"""CLI entry point for quantinvest."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="quantinvest",
        description="Quantitative Investment Framework",
    )
    subparsers = parser.add_subparsers(dest="command")

    # backtest subcommand
    bp = subparsers.add_parser("backtest", help="Run a backtest")
    bp.add_argument("--symbol", required=True, help="Stock symbol (e.g. 600519.SH)")
    bp.add_argument("--strategy", default="macross", choices=["macross", "macd", "bollinger", "turtle", "alpha", "reversal", "breakout", "costcross"])
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

    # web subcommand
    wbp = subparsers.add_parser("web", help="Start the web dashboard")
    wbp.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    wbp.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

    args = parser.parse_args()
    if args.command == "backtest":
        _run_backtest(args)
    elif args.command == "data":
        _fetch_data(args)
    elif args.command == "watchlist":
        _manage_watchlist(args)
    elif args.command == "web":
        _run_web(args)
    else:
        parser.print_help()


def _run_backtest(args) -> None:
    from quantinvest.data import QuantData
    from quantinvest.strategy import (
        MACrossStrategy, MACDStrategy, BollingerStrategy,
        TurtleStrategy, AlphaStrategy, ReversalStrategy, BreakoutStrategy,
        CostCrossStrategy,
    )
    from quantinvest.backtest import BacktestEngine

    strategy_map = {
        "macross": MACrossStrategy,
        "macd": MACDStrategy,
        "bollinger": BollingerStrategy,
        "turtle": TurtleStrategy,
        "alpha": AlphaStrategy,
        "reversal": ReversalStrategy,
        "breakout": BreakoutStrategy,
        "costcross": CostCrossStrategy,
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


def _run_web(args) -> None:
    """Start the web dashboard: FastAPI backend + static frontend."""
    project_root = Path(__file__).resolve().parent.parent
    frontend_dist = project_root / "web" / "frontend" / "dist"

    if not frontend_dist.exists():
        print("[quantinvest] Frontend not built. Building now...")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(project_root / "web" / "frontend"),
        )
        if result.returncode != 0:
            print("[quantinvest] Build failed. Run 'npm run build' manually.")
            sys.exit(1)

    # Mount static files and start uvicorn
    from fastapi.staticfiles import StaticFiles

    from web.backend.app import app

    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

    print(f"[quantinvest] Dashboard running at http://{args.host}:{args.port}")
    print("[quantinvest] Press Ctrl+C to stop\n")

    import uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
