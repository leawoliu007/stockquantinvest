"""FastAPI application with watchlist, strategy, and backtest endpoints."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import pandas as pd

# Inject proxy for akshare / yfinance network requests (this machine needs it)
_PROXY = os.environ.get("HTTP_PROXY", "http://192.168.0.114:7890")
os.environ.setdefault("HTTP_PROXY", _PROXY)
os.environ.setdefault("HTTPS_PROXY", _PROXY)
os.environ.setdefault("http_proxy", _PROXY)
os.environ.setdefault("https_proxy", _PROXY)

from quantinvest.config import load_config
from quantinvest.data import QuantData, QuantDB
from quantinvest.backtest import BacktestEngine
from quantinvest.strategy import MACrossStrategy, MACDStrategy, BollingerStrategy

app = FastAPI(title="QuantInvest Web", version="0.1.0")

# Strategy registry
STRATEGY_MAP: dict[str, Any] = {
    "macross": MACrossStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerStrategy,
}

# Supported frequencies
SUPPORTED_FREQS = ["daily", "weekly", "monthly", "30min", "15min", "60min", "5min", "1min"]


# --- Pydantic models ---

class WatchlistItem(BaseModel):
    symbol: str
    name: str = ""
    market: str = ""


class AnalyzeRequest(BaseModel):
    symbol: str
    freq: str = "daily"
    strategy: str = "macross"
    start: Optional[str] = None
    end: Optional[str] = None
    cash: float = 100_000.0


# --- Helper: get DB connection ---

def _get_db() -> QuantDB:
    cfg = load_config()
    db = QuantDB(cfg.db_path)
    # Ensure watchlist JSON is imported
    db.save_watchlist_from_file(cfg.watchlist_file)
    return db


# --- Resolve Symbol API ---

@app.get("/api/resolve-symbol")
def resolve_symbol(code: str = Query(..., description="Raw stock code (e.g. 600519 or 510300)")):
    """Try common market suffixes and return the first one that has data."""
    # Determine candidate suffixes based on input pattern
    suffixes = _guess_suffixes(code)

    from quantinvest.data import BaoStockData, AkShareData, YFinanceData

    results = []
    for suffix in suffixes:
        full_symbol = f"{code}{suffix}"
        # HK stocks use akshare stock_hk_hist directly
        if suffix == ".HK":
            try:
                import akshare as ak
                hk_code = code.zfill(5)  # pad to 5 digits for akshare
                df = ak.stock_hk_hist(symbol=hk_code, period="daily",
                    start_date=(date.today() - timedelta(days=7)).strftime("%Y%m%d"),
                    end_date=date.today().strftime("%Y%m%d"))
                if not df.empty and len(df) >= 2:
                    results.append({"symbol": full_symbol, "source": "akshare_hk"})
            except Exception:
                pass
        # US stocks use yfinance
        elif suffix == ".US":
            try:
                provider = YFinanceData()
                df = provider.fetch(full_symbol, start=(date.today() - timedelta(days=7)).strftime("%Y-%m-%d"), end=date.today().strftime("%Y-%m-%d"))
                if not df.empty and len(df) >= 2:
                    results.append({"symbol": full_symbol, "source": "yfinance"})
            except Exception:
                pass
        # A-share / ETF — try baostock first, then akshare
        else:
            for src_cls in [BaoStockData, AkShareData]:
                try:
                    provider = src_cls()
                    df = provider.fetch(full_symbol, start=(date.today() - timedelta(days=7)).strftime("%Y-%m-%d"), end=date.today().strftime("%Y-%m-%d"))
                    if not df.empty and len(df) >= 2:
                        results.append({"symbol": full_symbol, "source": src_cls.__name__})
                        break
                except Exception:
                    continue

    if len(results) == 0:
        raise HTTPException(404, f"No data found for code '{code}' in any market")
    if len(results) == 1:
        return {"symbol": results[0]["symbol"], "ambiguous": False}
    # Multiple matches — return all for frontend to pick
    return {"symbol": results[0]["symbol"], "ambiguous": True, "alternatives": [r["symbol"] for r in results]}


def _guess_suffixes(code: str) -> list[str]:
    """Order suffix candidates by likelihood based on code pattern."""
    # Already has suffix — return as-is
    if "." in code:
        return [code.split(".")[1].upper()]

    # US stocks contain letters
    if any(c.isalpha() for c in code):
        return [".US"]

    # A-share patterns
    num = code.lstrip("0") or "0"
    first_digit = code[0] if code else ""

    if first_digit in ("6",):  # Shanghai main + STAR (688)
        return [".SH", ".SZ", ".HK", ".BJ"]
    if first_digit in ("0",):  # Shenzhen main
        return [".SZ", ".SH", ".HK", ".BJ"]
    if first_digit == "3":  # GEM / ChiNext
        return [".SZ", ".SH", ".HK", ".BJ"]
    if first_digit in ("8", "4"):  # BSE / NEEQ
        return [".BJ", ".SH", ".SZ", ".HK"]

    # ETF / ambiguous (5, 1, 2, 7, 9 prefix or HK-style 4-5 digits)
    if len(code) == 6:
        return [".SH", ".SZ", ".BJ", ".HK"]
    # HK-style (typically 4-5 digits starting with 0)
    if len(code) <= 5:
        return [".HK", ".US", ".SH", ".SZ"]

    return [".SH", ".SZ", ".HK", ".US", ".BJ"]


# --- Watchlist API ---

@app.get("/api/watchlist")
def get_watchlist():
    """Return all watchlist entries."""
    db = _get_db()
    try:
        items = db.get_watchlist()
    finally:
        db.close()
    return items


@app.post("/api/watchlist")
def add_watchlist(item: WatchlistItem):
    """Add a symbol to the watchlist."""
    db = _get_db()
    try:
        db.add_watchlist(item.symbol, item.name, item.market)
    finally:
        db.close()
    return {"status": "ok", "symbol": item.symbol}


@app.delete("/api/watchlist/{symbol}")
def remove_watchlist(symbol: str):
    """Remove a symbol from the watchlist."""
    db = _get_db()
    try:
        db.remove_watchlist(symbol)
    finally:
        db.close()
    return {"status": "ok", "symbol": symbol}


# --- Strategies API ---

@app.get("/api/strategies")
def list_strategies():
    """List all available strategy names."""
    return list(STRATEGY_MAP.keys())


# --- Analyze / Backtest API ---

@app.get("/api/analyze")
def run_analyze(
    symbol: str = Query(..., description="Stock symbol (e.g. 600519.SH)"),
    freq: str = Query("daily", description="Data frequency"),
    strategy: str = Query("macross", description="Strategy name"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    cash: float = Query(100_000.0, description="Initial cash"),
):
    """Run backtest and return kline data, equity curve, and trade signals."""
    if strategy not in STRATEGY_MAP:
        raise HTTPException(400, f"Unknown strategy: {strategy}. Choose from {list(STRATEGY_MAP.keys())}")

    if freq not in SUPPORTED_FREQS:
        raise HTTPException(400, f"Unsupported frequency: {freq}. Choose from {SUPPORTED_FREQS}")

    # Default date range
    if not end:
        end = date.today().strftime("%Y-%m-%d")
    if not start:
        start = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    # Fetch data — try preferred source first, fallback to others on failure
    df = pd.DataFrame()
    error_msg = ""

    # Determine which sources to try
    if symbol.endswith((".SH", ".SZ")):
        source_order = ["baostock", "akshare"]  # A-stock: baostock first (direct connection)
    elif symbol.endswith((".HK", ".US")):
        source_order = ["yfinance", "akshare"]
    else:
        source_order = ["baostock", "akshare", "yfinance"]

    from quantinvest.data import AkShareData, BaoStockData, YFinanceData

    _SOURCE_CLS = {
        "akshare": AkShareData,
        "baostock": BaoStockData,
        "yfinance": YFinanceData,
    }

    for src_name in source_order:
        src_cls = _SOURCE_CLS.get(src_name)
        if not src_cls:
            continue
        try:
            provider = src_cls()
            df = provider.fetch(symbol, start=start, end=end, freq=freq)
            if not df.empty:
                break
        except Exception as e:
            error_msg = f"{src_name}: {e}"
            continue

    if df.empty:
        raise HTTPException(502, f"All data sources failed for {symbol}. Last error: {error_msg}")

    # Run backtest
    try:
        engine = BacktestEngine(df, cash=cash)
        engine.run(STRATEGY_MAP[strategy])
    except Exception as e:
        raise HTTPException(500, f"Backtest failed: {e}")

    # Build response
    kline_rows = []
    for _, row in df.reset_index().iterrows():
        dt_val = row.get("date", "")
        if hasattr(dt_val, "strftime"):
            dt_val = dt_val.strftime("%Y-%m-%d")
        kline_rows.append({
            "date": str(dt_val),
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "close": float(row.get("close", 0)),
            "volume": float(row.get("volume", 0)),
        })

    # Convert equity curve to return %
    equity_series = engine.get_equity_curve()
    returns_curve = []
    initial_cash = cash
    for dt_val, val in equity_series.items():
        if hasattr(dt_val, "strftime"):
            dt_val = dt_val.strftime("%Y-%m-%d")
        ret_pct = (val - initial_cash) / initial_cash * 100
        returns_curve.append({"date": str(dt_val), "value": round(ret_pct, 2)})

    # Buy-and-hold benchmark: hold from first close to each close
    bh_benchmark = []
    if len(kline_rows) >= 1:
        first_price = kline_rows[0]["close"]
        for row in kline_rows:
            bh_pct = (row["close"] - first_price) / first_price * 100
            bh_benchmark.append({"date": row["date"], "value": round(bh_pct, 2)})

    # Trade signals with position state
    signals_df = engine.get_trade_signals()
    signals_with_state = []
    current_position: Optional[str] = None  # date of last BUY or None

    # Build a set of all dates from kline for filling position
    all_dates = [r["date"] for r in kline_rows]

    # Enrich signals with position state
    signal_dates = {}
    if not signals_df.empty:
        for _, srow in signals_df.iterrows():
            s_date = srow["date"]
            if hasattr(s_date, "strftime"):
                s_date = s_date.strftime("%Y-%m-%d")
            signal_dates[str(s_date)] = str(srow["signal"])

    # For each kline date, compute position state
    position_map: dict[str, str] = {}
    running_pos: Optional[str] = None  # "BUY" date or None
    for d in all_dates:
        if d in signal_dates:
            if signal_dates[d] == "BUY":
                running_pos = "LONG"
            elif signal_dates[d] == "SELL":
                running_pos = "FLAT"
        position_map[d] = running_pos or "FLAT"

    # Build signals list (only on BUY/SELL dates) with price lookup
    signal_price_map: dict[str, float] = {}
    if not signals_df.empty:
        for _, srow in signals_df.iterrows():
            s_date = srow["date"]
            if hasattr(s_date, "strftime"):
                s_date_str = s_date.strftime("%Y-%m-%d")
            else:
                s_date_str = str(s_date)
            signal_price_map[s_date_str] = float(srow["price"])

    for d, sig_type in signal_dates.items():
        signals_with_state.append({
            "date": d,
            "signal": sig_type,
            "price": signal_price_map.get(d, 0),
        })

    # Completed trades
    trades_df = engine.get_completed_trades()
    completed_trades = []
    if not trades_df.empty:
        for _, trow in trades_df.iterrows():
            bd = trow["buy_date"]
            sd = trow["sell_date"]
            if hasattr(bd, "strftime"):
                bd = bd.strftime("%Y-%m-%d")
            if hasattr(sd, "strftime"):
                sd = sd.strftime("%Y-%m-%d")
            completed_trades.append({
                "buy_date": str(bd),
                "sell_date": str(sd),
                "buy_price": float(trow["buy_price"]),
                "sell_price": float(trow["sell_price"]),
                "pnl": float(trow["pnl"]),
                "is_profitable": bool(trow["is_profitable"]),
            })

    report = engine.get_report()
    final_value = engine.cerebro.broker.getvalue()
    total_return = (final_value - cash) / cash * 100

    return {
        "symbol": symbol,
        "freq": freq,
        "strategy": strategy,
        "bars": len(kline_rows),
        "kline": kline_rows,
        "returns_curve": returns_curve,
        "bh_benchmark": bh_benchmark,
        "signals": signals_with_state,
        "position_map": position_map,
        "completed_trades": completed_trades,
        "report": report,
        "final_value": final_value,
        "total_return_pct": round(total_return, 2),
    }
