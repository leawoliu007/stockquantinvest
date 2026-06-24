from __future__ import annotations

import datetime as dt

import baostock as bs
import pandas as pd


class BaoStockData:
    """Fetch A-stock historical data from BaoStock."""

    def fetch(
        self,
        symbol: str,
        start: str | dt.date = "2020-01-01",
        end: str | dt.date = dt.date.today().strftime("%Y-%m-%d"),
        freq: str = "daily",
    ) -> pd.DataFrame:
        if not bs.login().error_code == "0":
            raise RuntimeError("baostock login failed")
        try:
            code = self._to_bao_symbol(symbol)
            rs = bs.query_history_k_data_plus(
                code,
                "date,open,high,low,close,volume",
                start_date=str(start),
                end_date=str(end),
                frequency={"daily": "d", "weekly": "w", "monthly": "m"}[freq],
                adjustflag="2",  # 前复权
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            df = pd.DataFrame(rows, columns=rs.fields)
            return self._clean(df)
        finally:
            bs.logout()

    def fetch_realtime(self, symbol: str) -> pd.DataFrame:
        """Fetch real-time stock quote from BaoStock."""
        code = self._to_bao_symbol(symbol)
        rs = bs.query_real_time_quotes(code)
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
        return pd.DataFrame(rows, columns=rs.fields)

    @staticmethod
    def _to_bao_symbol(symbol: str) -> str:
        code = symbol.split(".")[0]
        suffix = symbol.split(".")[-1]
        return f"sh.{code}" if suffix == "SH" else f"sz.{code}"

    @staticmethod
    def _clean(df: pd.DataFrame) -> pd.DataFrame:
        cols = [
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
        df = df[cols].copy()
        df["date"] = pd.to_datetime(df["date"])
        for c in cols[1:]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.set_index("date").sort_index()
