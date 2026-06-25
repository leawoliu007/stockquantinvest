"""Example: 30-min kline backtest with SQLite cache for A-stock.

Usage:
    python3 examples/run_30min_backtest.py
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

os.environ.setdefault("HTTPS_PROXY", "http://192.168.0.114:7890")
os.environ.setdefault("HTTP_PROXY", "http://192.168.0.114:7890")

sys.path.insert(0, str(Path(__file__).parent.parent))

from quantinvest.data import QuantData, QuantDB
from quantinvest.strategy import MACDStrategy
from quantinvest.backtest import BacktestEngine
from quantinvest.viz.plotter import plot_kline, plot_equity_curve


def main() -> None:
    # A-stock symbol — change to your preferred ticker
    symbol = "600519.SH"  # 贵州茅台
    start = "2024-01-01"

    # Initialize DB and load watchlist from file
    db = QuantDB()
    db.save_watchlist_from_file(Path(__file__).parent.parent / "watchlist.json")
    print(f"Watchlist: {[w['symbol'] for w in db.get_watchlist()]}")

    # Fetch 30-min data with cache (incremental update)
    data = QuantData.get(symbol)
    latest_cached = db.get_latest_date(symbol, "30min")
    if latest_cached:
        print(f"Cache hit — latest cached date: {latest_cached}, fetching incremental data...")
    else:
        print("No cache — fetching full range...")

    df = data.fetch(symbol, start=start, end=dt.date.today(), freq="30min", use_cache=True)

    if len(df) < 30:
        print(f"Not enough 30-min data ({len(df)} bars). Try a different symbol or date range.")
        db.close()
        return

    print(f"Loaded {len(df)} 30-min bars for {symbol}")

    engine = BacktestEngine(df, cash=100_000.0)
    results = engine.run(MACDStrategy, fast=12, slow=26, signal=9, rsi_period=14)

    print(engine.get_report())

    # Generate charts
    output_dir = Path(__file__).parent.parent / "charts"
    output_dir.mkdir(exist_ok=True)

    df_copy = df.copy()
    indicators = {
        "MA5": df_copy["close"].rolling(5).mean(),
        "MA20": df_copy["close"].rolling(20).mean(),
        "MACD": results.macd.macd,
        "Signal": results.macd.signal,
    }
    plot_kline(
        df_copy,
        title=f"{symbol} — 30min MACD Strategy",
        indicators=indicators,
        completed_trades=engine.get_completed_trades(),
        output=output_dir / f"kline_{symbol.replace('.', '_')}_30min.png",
    )

    equity = engine.get_equity_curve()
    plot_equity_curve(
        equity,
        title=f"Equity Curve — {symbol} (30min)",
        output=output_dir / f"equity_{symbol.replace('.', '_')}_30min.png",
    )

    db.close()
    print(f"Charts saved to {output_dir}")


if __name__ == "__main__":
    main()
