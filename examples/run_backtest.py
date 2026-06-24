"""Example: run a backtest with MACD strategy and plot results."""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

# Set proxy via environment variable (or use .env file)
os.environ.setdefault("HTTPS_PROXY", "http://192.168.0.114:7890")
os.environ.setdefault("HTTP_PROXY", "http://192.168.0.114:7890")

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from quantinvest.data import QuantData
from quantinvest.strategy import MACDStrategy
from quantinvest.backtest import BacktestEngine
from quantinvest.viz.plotter import plot_kline, plot_equity_curve


def main() -> None:
    # Use a stock symbol — change to your preferred ticker
    symbol = "0700.HK"  # Tencent Holdings
    start = "2023-01-01"

    data = QuantData.get(symbol)
    df = data.fetch(symbol, start=start, end=dt.date.today())

    if len(df) < 30:
        print("Not enough data to backtest. Try a different symbol or date range.")
        return

    print(f"Loaded {len(df)} bars for {symbol}")

    engine = BacktestEngine(df, cash=100_000.0)
    results = engine.run(MACDStrategy, fast=12, slow=26, signal=9, rsi_period=14)

    print(engine.get_report())

    # Generate charts
    output_dir = Path(__file__).parent.parent / "charts"
    output_dir.mkdir(exist_ok=True)

    # 1. K-line with indicators (MA + MACD)
    df_copy = df.copy()
    indicators = {
        "MA5": df_copy["close"].rolling(5).mean(),
        "MA20": df_copy["close"].rolling(20).mean(),
        "MACD": results.macd.macd,
        "Signal": results.macd.signal,
    }
    plot_kline(
        df_copy,
        title=f"{symbol} — MACD Strategy",
        indicators=indicators,
        output=output_dir / f"kline_{symbol.replace('.', '_')}.png",
    )

    # 2. Equity curve
    equity = engine.get_equity_curve()
    plot_equity_curve(
        equity,
        title=f"Equity Curve — {symbol}",
        output=output_dir / f"equity_{symbol.replace('.', '_')}.png",
    )


if __name__ == "__main__":
    main()
