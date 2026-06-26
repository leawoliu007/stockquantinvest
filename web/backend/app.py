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
    strategy: str = "macross"


class StrategyUpdate(BaseModel):
    strategy: str


class AnalyzeRequest(BaseModel):
    symbol: str
    freq: str = "daily"
    strategy: str = "macross"
    start: Optional[str] = None
    end: Optional[str] = None
    cash: float = 100_000.0


# --- Helper: get DB connection ---

_db_instance: QuantDB | None = None

def _get_db() -> QuantDB:
    global _db_instance
    if _db_instance is None:
        cfg = load_config()
        _db_instance = QuantDB(cfg.db_path)
        # Import watchlist JSON only once at startup
        _db_instance.save_watchlist_from_file(cfg.watchlist_file)
    return _db_instance


# --- Resolve Symbol API ---

@app.get("/api/resolve-symbol")
def resolve_symbol(code: str = Query(..., description="Raw stock code (e.g. 600519 or 510300)")):
    """Resolve stock code to symbol+name. Check local DB first, then remote APIs."""
    # 1. Try local symbols table first (instant)
    db = _get_db()
    try:
        local_hits = db.search_symbols(code, limit=20)
        if local_hits:
            suffixes = _guess_suffixes(code)
            # Filter to candidates with matching suffix
            matched = [h for h in local_hits if any(h["ticker"].endswith(s) for s in suffixes)]
            if matched:
                hit = matched[0]
                db.close()
                return {"symbol": hit["ticker"], "name": hit["name"], "ambiguous": False}

            # If no exact suffix match, still return local hits as alternatives
            primary = local_hits[0]
            db.close()
            return {
                "symbol": primary["ticker"],
                "name": primary["name"],
                "ambiguous": len(local_hits) > 1,
                "alternatives": [h["ticker"] for h in local_hits[:5]],
            }
    finally:
        db.close()

    # 2. Fallback: remote data sources (slow)
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

    # Pick primary result and fetch stock name
    primary = results[0]
    symbol = primary["symbol"]
    name = _fetch_stock_name(symbol)

    if len(results) == 1:
        return {"symbol": symbol, "name": name, "ambiguous": False}
    # Multiple matches — return all for frontend to pick
    return {"symbol": symbol, "name": name, "ambiguous": True, "alternatives": [r["symbol"] for r in results]}


def _fetch_stock_name(symbol: str) -> str:
    """Query stock name from data sources based on symbol suffix."""
    code = symbol.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    try:
        if symbol.endswith((".SH", ".SZ", ".BJ")):
            import baostock as bs
            # Map suffix to baostock prefix
            prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}[symbol.split(".")[-1]]
            bs_code = f"{prefix}.{code.zfill(6)}"
            lg = bs.login()
            try:
                rs = bs.query_stock_basic(code=bs_code)
                if rs.error_msg == "success":
                    while rs.next():
                        return rs.get_row_data()[1]  # code_name
            finally:
                bs.logout()
        elif symbol.endswith(".US"):
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol.replace(".US", ""))
                info = ticker.info
                if info and "shortName" in info:
                    return info["shortName"]
            except Exception:
                pass
        elif symbol.endswith(".HK"):
            try:
                import akshare as ak
                df = ak.stock_hk_spot_em()
                row = df[df["代码"] == code]
                if not row.empty:
                    return str(row.iloc[0]["名称"])
            except Exception:
                pass
    except Exception:
        pass
    return code  # fallback to code itself


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
        db.add_watchlist(item.symbol, item.name, item.market, item.strategy)
    finally:
        db.close()
    return {"status": "ok", "symbol": item.symbol}


@app.patch("/api/watchlist/{symbol}")
def update_watchlist_strategy(symbol: str, body: StrategyUpdate):
    """Update strategy for a watchlist item."""
    db = _get_db()
    try:
        db.update_strategy(symbol, body.strategy)
    finally:
        db.close()
    return {"status": "ok", "symbol": symbol, "strategy": body.strategy}


@app.delete("/api/watchlist/{symbol}")
def remove_watchlist(symbol: str):
    """Remove a symbol from the watchlist."""
    db = _get_db()
    try:
        db.remove_watchlist(symbol)
    finally:
        db.close()
    return {"status": "ok", "symbol": symbol}


# --- Quote API ---

def _get_fallback_quote(symbol: str) -> dict:
    """Fallback: get latest price from historical data (baostock / akshare)."""
    from quantinvest.data import BaoStockData, AkShareData
    from datetime import date, timedelta

    end_date = date.today().strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")

    for cls in ([BaoStockData] if symbol.endswith((".SH", ".SZ")) else []):
        try:
            provider = cls()
            df = provider.fetch(symbol, start=start_date, end=end_date, freq="daily")
            if not df.empty and len(df) >= 2:
                price = round(float(df["close"].iloc[-1]), 3)
                prev_close = round(float(df["close"].iloc[-2]), 3)
                change_pct = round((price - prev_close) / prev_close * 100, 2)
                return {"price": price, "change_pct": change_pct, "prev_close": prev_close}
        except Exception:
            continue

    try:
        provider = AkShareData()
        df = provider.fetch(symbol, start=start_date, end=end_date, freq="daily")
        if not df.empty and len(df) >= 2:
            price = round(float(df["close"].iloc[-1]), 3)
            prev_close = round(float(df["close"].iloc[-2]), 3)
            change_pct = round((price - prev_close) / prev_close * 100, 2)
            return {"price": price, "change_pct": change_pct, "prev_close": prev_close}
    except Exception:
        pass

    return {"price": None, "change_pct": None, "prev_close": None}


@app.get("/api/quote")
def get_quotes(symbols: str = Query(..., description="Comma-separated symbols (e.g. 600519.SH,0700.HK)")):
    """Fetch real-time price and daily change % for given symbols."""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    results = []

    # Batch fetch A-share spot data via akshare
    a_symbols = [s for s in symbol_list if s.endswith((".SH", ".SZ"))]
    other_symbols = [s for s in symbol_list if not s.endswith((".SH", ".SZ"))]

    # A-share: use akshare real-time snapshot
    if a_symbols:
        try:
            import akshare as ak
            # Fetch stocks
            stock_codes = []
            etf_codes = []
            for s in a_symbols:
                code = s.replace(".SH", "").replace(".SZ", "")
                # ETF codes start with 51/15/16/56 etc.
                if code[:2] in ("51", "15", "16", "56", "10", "50", "12"):
                    etf_codes.append(code)
                else:
                    stock_codes.append(code)

            spot_results = {}
            if stock_codes:
                try:
                    df = ak.stock_zh_a_spot_em()
                    for code in stock_codes:
                        row = df[df["代码"] == code]
                        if not row.empty:
                            r = row.iloc[0]
                            sym = code + ".SH" if code.startswith(("6", "9")) else code + ".SZ"
                            spot_results[sym] = {
                                "price": round(float(r.get("最新价", 0)), 3),
                                "change_pct": round(float(r.get("涨跌幅", 0)), 2),
                                "prev_close": round(float(r.get("昨收", 0)), 3),
                            }
                except Exception:
                    pass

            if etf_codes:
                try:
                    df = ak.fund_etf_spot_em()
                    for code in etf_codes:
                        row = df[df["代码"] == code]
                        if not row.empty:
                            r = row.iloc[0]
                            sym = code + ".SH" if code.startswith(("5", "1")) else code + ".SZ"
                            spot_results[sym] = {
                                "price": round(float(r.get("最新价", 0)), 3),
                                "change_pct": round(float(r.get("涨跌幅", 0)), 2),
                                "prev_close": round(float(r.get("昨收", 0)), 3),
                            }
                except Exception:
                    pass

            for s in a_symbols:
                if s in spot_results:
                    results.append({"symbol": s, **spot_results[s]})
                else:
                    # Fallback: fetch last 2 trading days via baostock / akshare historical
                    fallback = _get_fallback_quote(s)
                    results.append({"symbol": s, **fallback})
        except Exception:
            for s in a_symbols:
                results.append({"symbol": s, "price": None, "change_pct": None, "prev_close": None})

    # HK / US: use yfinance (with proxy if available)
    import os
    proxy = os.environ.get("http_proxy", "http://192.168.0.114:7890")
    os.environ["HTTP_PROXY"] = proxy
    os.environ["HTTPS_PROXY"] = proxy

    for symbol in other_symbols:
        try:
            import yfinance as yf
            ticker_sym = symbol.replace(".US", "")
            ticker = yf.Ticker(ticker_sym)
            info = ticker.fast_info
            price = round(info.last_price, 3) if hasattr(info, "last_price") else None

            # Get previous close for change %
            prev_close = None
            change_pct = None
            if price:
                try:
                    hist = ticker.history(period="5d")
                    if not hist.empty and len(hist) >= 2:
                        prev_close = round(float(hist["Close"].iloc[-2]), 3)
                        change_pct = round((price - prev_close) / prev_close * 100, 2)
                    elif not hist.empty:
                        prev_close = round(float(hist["Close"].iloc[-1]), 3)
                except Exception:
                    pass

            results.append({"symbol": symbol, "price": price, "change_pct": change_pct, "prev_close": prev_close})
        except Exception:
            results.append({"symbol": symbol, "price": None, "change_pct": None, "prev_close": None})

    return results


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
    strategy: Optional[str] = Query(None, description="Strategy name (defaults to watchlist setting)"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    cash: float = Query(100_000.0, description="Initial cash"),
):
    """Run backtest and return kline data, equity curve, and trade signals."""
    # Default strategy from watchlist DB, fallback to 'macross'
    if not strategy:
        db = _get_db()
        try:
            row = db._active_conn.execute(
                "SELECT strategy FROM watchlist WHERE symbol = ?", (symbol,)
            ).fetchone()
            strategy = row["strategy"] if row and row["strategy"] else "macross"
        finally:
            db.close()

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

    # Filter out zero/negative price rows (bad data from baostock)
    mask = (df["close"] > 0) & (df["open"] > 0) & (df["high"] > 0) & (df["low"] > 0)
    df = df[mask].copy()
    if df.empty:
        raise HTTPException(502, f"No valid data for {symbol} after filtering zero prices.")

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

    # Compute stats for saving
    wins = [t for t in completed_trades if t["is_profitable"]]
    losses = [t for t in completed_trades if not t["is_profitable"]]
    win_rate = len(completed_trades) > 0 and len(wins) / len(completed_trades) * 100 or 0
    avg_win = len(wins) > 0 and sum(w["pnl"] for w in wins) / len(wins) or 0
    avg_loss = len(losses) > 0 and abs(sum(l["pnl"] for l in losses) / len(losses)) or 1
    pl_ratio = avg_loss > 0 and (avg_win / avg_loss) or 0
    avg_pos_ret = len(wins) > 0 and sum((w["sell_price"] - w["buy_price"]) / w["buy_price"] * 100 for w in wins) / len(wins) or 0
    avg_neg_ret = len(losses) > 0 and sum((l["sell_price"] - l["buy_price"]) / l["buy_price"] * 100 for l in losses) / len(losses) or 0

    # Save to database
    try:
        db = _get_db()
        try:
            db.save_backtest_result(
                symbol=symbol, freq=freq, strategy=strategy,
                total_return_pct=round(total_return, 2), final_value=final_value,
                trade_count=len(completed_trades),
                win_count=len(wins), loss_count=len(losses),
                win_rate=win_rate, pl_ratio=pl_ratio,
                avg_positive_return=avg_pos_ret, avg_negative_return=avg_neg_ret,
                trades=completed_trades,
                kline=kline_rows,
                returns_curve=returns_curve,
            )
        finally:
            db.close()
    except Exception:
        pass  # Don't fail the response if saving fails

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


# --- Backtest Cache API ---

@app.get("/api/backtest-cached/{symbol}")
def get_cached_backtest(symbol: str):
    """Get the most recent saved backtest result for a symbol, or null."""
    db = _get_db()
    try:
        results = db.get_backtest_history(symbol=symbol, limit=1)
        if not results:
            return None
        row = results[0]
        detail = db.get_backtest_result(row["id"])
    finally:
        db.close()
    return detail


@app.delete("/api/backtest-cached/{symbol}")
def clear_cached_backtest(symbol: str):
    """Clear all cached backtest results for a symbol."""
    db = _get_db()
    try:
        db.delete_backtest_by_symbol(symbol)
    finally:
        db.close()
    return {"status": "ok", "symbol": symbol}


# --- Backtest History API ---

@app.get("/api/backtest-history")
def get_backtest_history(
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    """Get backtest result history."""
    db = _get_db()
    try:
        results = db.get_backtest_history(symbol=symbol, limit=limit)
    finally:
        db.close()
    return results


@app.get("/api/backtest-history/{result_id}")
def get_backtest_result(result_id: int):
    """Get a single backtest result with trades detail."""
    db = _get_db()
    try:
        result = db.get_backtest_result(result_id)
    finally:
        db.close()
    if result is None:
        raise HTTPException(404, f"Backtest result {result_id} not found")
    return result


@app.delete("/api/backtest-history/{result_id}")
def delete_backtest_result(result_id: int):
    """Delete a backtest result."""
    db = _get_db()
    try:
        db.delete_backtest_result(result_id)
    finally:
        db.close()
    return {"status": "ok", "id": result_id}


# --- Symbol Database Update API ---

@app.post("/api/update-symbols")
def update_symbols():
    """Trigger a full refresh of the symbols database from all sources."""
    import subprocess as subp
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    result = {"status": "ok", "sources": {}}

    # 1. Fetch A-share stocks + ETFs via baostock
    try:
        r = subp.run(
            ["python3", str(project_root / "examples" / "fetch_a_stock_list.py")],
            capture_output=True, text=True, timeout=120, cwd=str(project_root),
        )
        if r.returncode == 0:
            result["sources"]["a_share"] = "ok"
        else:
            result["sources"]["a_share"] = f"error: {r.stderr.strip()[-200:]}"
    except Exception as e:
        result["sources"]["a_share"] = f"error: {e}"

    # 2. Fetch index constituents (S&P 500, NASDAQ-100, HSI) via Wikipedia
    try:
        r = subp.run(
            ["python3", str(project_root / "examples" / "fetch_index_constituents.py")],
            capture_output=True, text=True, timeout=120, cwd=str(project_root),
        )
        if r.returncode == 0:
            result["sources"]["indices"] = "ok"
        else:
            result["sources"]["indices"] = f"error: {r.stderr.strip()[-200:]}"
    except Exception as e:
        result["sources"]["indices"] = f"error: {e}"

    # 3. Import all CSVs into data.db
    try:
        r = subp.run(
            ["python3", str(project_root / "examples" / "import_symbols.py")],
            capture_output=True, text=True, timeout=60, cwd=str(project_root),
        )
        if r.returncode == 0:
            # Parse total count from output
            output = r.stdout.strip()
            result["sources"]["import"] = "ok"
            for line in output.split("\n"):
                if "Total:" in line:
                    result["total"] = line.strip()
                    break
        else:
            result["sources"]["import"] = f"error: {r.stderr.strip()[-200:]}"
    except Exception as e:
        result["sources"]["import"] = f"error: {e}"

    return result
