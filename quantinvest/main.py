"""CLI entry point for quantinvest."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="quantinvest",
        description="Quantitative Investment Framework",
    )
    subparsers = parser.add_subparsers(dest="command")

    # backtest subcommand
    bp = subparsers.add_parser("backtest", help="Run a backtest")
    bp.add_argument("--symbol", required=True, help="Stock symbol (e.g. 600519.SH)")
    bp.add_argument("--strategy", default="macross", choices=["macross", "macd", "bollinger"])
    bp.add_argument("--start", default="2020-01-01")
    bp.add_argument("--end", default=None)
    bp.add_argument("--cash", type=float, default=100_000.0)
    bp.add_argument("--output", help="Save chart to file")

    # data subcommand
    dp = subparsers.add_parser("data", help="Fetch and display data")
    dp.add_argument("--symbol", required=True)
    dp.add_argument("--source", choices=["akshare", "baostock", "yfinance"])

    args = parser.parse_args()
    if args.command == "backtest":
        _run_backtest(args)
    elif args.command == "data":
        _fetch_data(args)
    else:
        parser.print_help()


def _run_backtest(args) -> None:
    from quantinvest.data import QuantData
    from quantinvest.strategy import MACrossStrategy, MACDStrategy, BollingerStrategy
    from quantinvest.backtest import BacktestEngine

    strategy_map = {
        "macross": MACrossStrategy,
        "macd": MACDStrategy,
        "bollinger": BollingerStrategy,
    }

    data = QuantData.get(args.symbol)
    df = data.fetch(start=args.start, end=args.end or None)

    print(f"Loaded {len(df)} bars of {args.symbol}")
    engine = BacktestEngine(df, cash=args.cash)
    results = engine.run(strategy_map[args.strategy])

    print(engine.get_report())

    if args.output:
        engine.plot(filename=args.output)


def _fetch_data(args) -> None:
    from quantinvest.data import QuantData, AkShareData, BaoStockData, YFinanceData

    source_map = {
        "akshare": AkShareData,
        "baostock": BaoStockData,
        "yfinance": YFinanceData,
    }
    source_cls = source_map.get(args.source) or QuantData._infer_source(args.symbol)
    data = source_cls()

    df = data.fetch(args.symbol)
    print(df.tail(10))


if __name__ == "__main__":
    main()
