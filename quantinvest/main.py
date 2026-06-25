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

    # watchlist subcommand
    wp = subparsers.add_parser("watchlist", help="Manage watchlist")
    wp.add_argument("action", choices=["list", "add", "remove"], help="Action to perform")
    wp.add_argument("--symbol", help="Stock symbol to add or remove")
    wp.add_argument("--name", default="", help="Display name (for add)")

    args = parser.parse_args()
    if args.command == "backtest":
        _run_backtest(args)
    elif args.command == "data":
        _fetch_data(args)
    elif args.command == "watchlist":
        _manage_watchlist(args)
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


def _manage_watchlist(args) -> None:
    from quantinvest.data import QuantDB
    from quantinvest.config import load_config

    cfg = load_config()
    db = QuantDB(cfg.db_path)

    # Load from JSON file first time
    db.save_watchlist_from_file(cfg.watchlist_file)

    if args.action == "list":
        items = db.get_watchlist()
        if not items:
            print("Watchlist is empty.")
            db.close()
            return
        print(f"\n{'Symbol':<15} {'Name':<15} {'Market':<8} {'Added At'}")
        print("-" * 60)
        for item in items:
            print(f"{item['symbol']:<15} {item.get('name', ''):<15} {item.get('market', ''):<8} {item.get('added_at', '')}")
        print()

    elif args.action == "add":
        if not args.symbol:
            print("Error: --symbol is required for add action.")
            db.close()
            return
        db.add_watchlist(args.symbol, args.name)
        print(f"Added {args.symbol}" + (f" ({args.name})" if args.name else ""))

    elif args.action == "remove":
        if not args.symbol:
            print("Error: --symbol is required for remove action.")
            db.close()
            return
        db.remove_watchlist(args.symbol)
        print(f"Removed {args.symbol}")

    db.close()


if __name__ == "__main__":
    main()
