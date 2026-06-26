"""SQLite-based cache for watchlist and kline data."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


class QuantDB:
    """SQLite database for storing watchlist and kline data."""

    def __init__(self, db_path: str | Path = "data.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    # -- connection --

    @property
    def _active_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __del__(self) -> None:
        self.close()

    # -- schema --

    def _init_db(self) -> None:
        conn = self._active_conn
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol  TEXT PRIMARY KEY,
                name    TEXT,
                market  TEXT,
                strategy TEXT DEFAULT 'macross',
                added_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS kline (
                symbol TEXT NOT NULL,
                date   TEXT NOT NULL,
                freq   TEXT NOT NULL DEFAULT 'daily',
                open   REAL,
                high   REAL,
                low    REAL,
                close  REAL,
                volume REAL,
                PRIMARY KEY (symbol, date, freq)
            );

            CREATE TABLE IF NOT EXISTS symbols (
                ticker  TEXT PRIMARY KEY,
                name    TEXT,
                market  TEXT,
                sector  TEXT
            );
            """
        )
        conn.commit()
        # Migration: add strategy column if it doesn't exist
        try:
            conn.execute("ALTER TABLE watchlist ADD COLUMN strategy TEXT DEFAULT 'macross'")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

    # -- watchlist --

    def save_watchlist_from_file(self, filepath: str | Path) -> None:
        """Load watchlist entries from a JSON file and insert into DB."""
        path = Path(filepath)
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            items: list[dict[str, Any]] = json.load(f)
        conn = self._active_conn
        for item in items:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (symbol, name, market) VALUES (?, ?, ?)",
                (item["symbol"], item.get("name", ""), item.get("market", "")),
            )
        conn.commit()

    def get_watchlist(self) -> list[dict[str, Any]]:
        """Return all watchlist entries as a list of dicts."""
        rows = self._active_conn.execute(
            "SELECT symbol, name, market, strategy, added_at FROM watchlist ORDER BY added_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def add_watchlist(self, symbol: str, name: str = "", market: str = "", strategy: str = "macross") -> None:
        conn = self._active_conn
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (symbol, name, market, strategy) VALUES (?, ?, ?, ?)",
            (symbol, name, market, strategy),
        )
        conn.commit()

    def remove_watchlist(self, symbol: str) -> None:
        self._active_conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
        self._active_conn.commit()

    def update_strategy(self, symbol: str, strategy: str) -> None:
        """Update the strategy for a watchlist item."""
        self._active_conn.execute(
            "UPDATE watchlist SET strategy = ? WHERE symbol = ?", (strategy, symbol)
        )
        self._active_conn.commit()

    # -- kline --

    def get_latest_date(self, symbol: str, freq: str = "daily") -> date | None:
        """Return the latest cached date for a symbol+freq, or None."""
        row = self._active_conn.execute(
            "SELECT MAX(date) as max_date FROM kline WHERE symbol = ? AND freq = ?",
            (symbol, freq),
        ).fetchone()
        if row and row["max_date"]:
            return datetime.strptime(row["max_date"], "%Y-%m-%d").date()
        return None

    def fetch_cached(
        self, symbol: str, freq: str = "daily", start: str | date | None = None, end: str | date | None = None
    ) -> pd.DataFrame:
        """Return cached kline data as a DataFrame (same schema as fetcher output)."""
        conn = self._active_conn
        sql = "SELECT date, open, high, low, close, volume FROM kline WHERE symbol = ? AND freq = ?"
        params: list[str | date] = [symbol, freq]

        if start:
            sql += " AND date >= ?"
            params.append(str(start))
        if end:
            sql += " AND date <= ?"
            params.append(str(end))

        sql += " ORDER BY date"
        df = pd.read_sql_query(sql, conn, params=params, parse_dates=["date"])
        if df.empty:
            return df
        return df.set_index("date").sort_index()

    def save_kline(self, df: pd.DataFrame, symbol: str, freq: str = "daily") -> None:
        """Insert or replace kline rows. Expects df with date index and OHLCV columns."""
        conn = self._active_conn
        records = []
        for dt_val, row in df.iterrows():
            date_str = dt_val.strftime("%Y-%m-%d") if hasattr(dt_val, "strftime") else str(dt_val)
            records.append(
                (
                    symbol,
                    date_str,
                    freq,
                    float(row.get("open", 0)),
                    float(row.get("high", 0)),
                    float(row.get("low", 0)),
                    float(row.get("close", 0)),
                    float(row.get("volume", 0)),
                )
            )
        conn.executemany(
            """
            INSERT OR REPLACE INTO kline (symbol, date, freq, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.commit()

    def clear_kline(self, symbol: str, freq: str = "daily") -> None:
        """Remove all cached kline for a symbol+freq."""
        self._active_conn.execute(
            "DELETE FROM kline WHERE symbol = ? AND freq = ?", (symbol, freq)
        )
        self._active_conn.commit()

    # -- symbols --

    def import_symbols(self, df: pd.DataFrame, market: str) -> int:
        """Import stock symbols from a DataFrame.

        Args:
            df: DataFrame with 'ticker' and 'name' columns.
            market: Market tag (e.g. 'CN', 'HK', 'US').

        Returns:
            Number of rows inserted/updated.
        """
        conn = self._active_conn
        records = []
        for _, row in df.iterrows():
            ticker = str(row.get("ticker", ""))
            name = str(row.get("name", ""))
            sector = str(row.get("sector", "")) if "sector" in df.columns and pd.notna(row.get("sector")) else ""
            records.append((ticker, name, market, sector))

        conn.executemany(
            "INSERT OR REPLACE INTO symbols (ticker, name, market, sector) VALUES (?, ?, ?, ?)",
            records,
        )
        conn.commit()
        return len(records)

    def search_symbols(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search symbols by ticker or name (fuzzy match).

        Priority: exact ticker match > ticker starts with keyword > fuzzy match.
        """
        like = f"%{keyword}%"
        start = f"{keyword}%"
        rows = self._active_conn.execute(
            """SELECT ticker, name, market FROM symbols
               WHERE ticker LIKE ? OR ticker LIKE ? OR name LIKE ?
               ORDER BY
                 CASE
                   WHEN ticker = ? THEN 0
                   WHEN ticker LIKE ? THEN 1
                   WHEN ticker LIKE ? THEN 2
                   ELSE 3
                 END,
                 market,
                 name
               LIMIT ?""",
            (like, start, like, keyword, f"{keyword}.%", start, limit),
        ).fetchall()
        return [dict(r) for r in rows]
