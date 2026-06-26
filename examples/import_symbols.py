#!/usr/bin/env python3
"""Import stock symbol CSVs into data.db for fast local search."""

import pandas as pd
from pathlib import Path
from quantinvest.data.database import QuantDB


def main():
    db = QuantDB("data.db")
    project_root = Path(__file__).resolve().parent.parent

    csv_files = {
        "a_stock_codes.csv": "CN",
        "sp500_constituents.csv": "US",
        "nasdaq100_constituents.csv": "US",
        "hsi_constituents.csv": "HK",
    }

    total = 0
    for csv_name, market in csv_files.items():
        csv_path = project_root / csv_name
        if not csv_path.exists():
            print(f"[SKIP] {csv_name} not found")
            continue

        df = pd.read_csv(csv_path)
        # Ensure 'ticker' column exists (a_stock_codes.csv uses 'code')
        if "code" in df.columns and "ticker" not in df.columns:
            df.rename(columns={"code": "ticker"}, inplace=True)

        count = db.import_symbols(df, market)
        print(f"[OK] {csv_name}: {count} symbols -> {market}")
        total += count

    # Add index on name for fast fuzzy search
    db._active_conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)")
    db._active_conn.commit()

    print(f"\nTotal: {total} symbols imported into data.db")

    # Quick test
    results = db.search_symbols("腾讯", limit=5)
    print(f"\nSearch '腾讯': {results}")
    results = db.search_symbols("600519", limit=5)
    print(f"Search '600519': {results}")

    db.close()


if __name__ == "__main__":
    main()
