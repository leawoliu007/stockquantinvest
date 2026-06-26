#!/usr/bin/env python3
"""Fetch complete A-share stock list (individual stocks + ETFs) from BaoStock."""

import baostock as bs
import pandas as pd
from datetime import date, timedelta


def _latest_trade_day() -> str:
    """Find the latest trading day by probing BaoStock backwards."""
    bs.login()
    try:
        for i in range(1, 8):
            d = (date.today() - timedelta(days=i)).strftime("%Y-%m-%d")
            rs = bs.query_all_stock(day=d)
            if rs.error_code == "0":
                # Quick check: try to read first row
                if rs.next():
                    return d
        return date.today().strftime("%Y-%m-%d")
    finally:
        bs.logout()


def fetch_a_stock_list(day: str = None, output_path: str = "a_stock_codes.csv") -> pd.DataFrame:
    """
    Fetch all A-share stocks and ETFs from BaoStock.

    Args:
        day: Trading date string (e.g. '2026-06-25'). Defaults to latest trading day.
        output_path: CSV file path to save results.

    Returns:
        DataFrame with columns ['code', 'name'] in standard format (e.g. 600000.SH)
    """
    if day is None:
        day = _latest_trade_day()

    bs.login()
    try:
        rs = bs.query_all_stock(day=day)
        data_list = []
        while rs.error_code == "0" and rs.next():
            data_list.append(rs.get_row_data())
        df = pd.DataFrame(data_list, columns=rs.fields)

        # Filter: individual stocks + ETFs
        #   sh.6xxxxx(6位)=上交所主板, sh.9xxxxx(6位)=北交所
        #   sz.0xxxxx(6位)=深交所主板, sz.3xxxxx(6位)=创业板
        #   sh.51xxxx(5位)=上交所ETF,  sz.15xxx(5位)=深交所ETF
        pattern = r"^(?:sh\.(?:6|9)\d{5}|sh\.51\d{4}|sz\.(?:0[0-2]\d{4}|3\d{5}|15\d{4}))$"
        mask = df["code"].str.match(pattern)
        result = df[mask][["code", "code_name"]].copy()
        result.columns = ["code", "name"]

        # Convert to standard format: sh.600000 -> 600000.SH
        def fix_code(c):
            if c.startswith("sh."):
                return c[3:] + ".SH"
            if c.startswith("sz."):
                return c[3:] + ".SZ"
            return c

        result["code"] = result["code"].apply(fix_code)
        result.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"[fetch_a_stock_list] Saved {len(result)} records to {output_path}")
        return result
    finally:
        bs.logout()


if __name__ == "__main__":
    df = fetch_a_stock_list()

    stocks = df[~df["code"].str.startswith(("51", "15"))]
    etfs = df[df["code"].str.startswith(("51", "15"))]
    print(f"\nA股个股: {len(stocks)} 只")
    print(f"ETF: {len(etfs)} 只")
    print(f"合计: {len(df)} 条")
