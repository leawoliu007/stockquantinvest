#!/usr/bin/env python3
"""Fetch major index constituents (S&P 500, NASDAQ-100, Hang Seng Index) via Wikipedia + yfinance."""

import os
import io
import urllib.request
import pandas as pd

# Set proxy for yfinance
os.environ["http_proxy"] = "http://192.168.0.114:7890"
os.environ["https_proxy"] = "http://192.168.0.114:7890"


def _fetch_url(url: str) -> str:
    """Fetch URL with User-Agent to avoid 403."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")

# Wikipedia tables for index constituents
WIKI_TABLES = {
    "sp500": {
        "url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "table_idx": 0,
        "ticker_col": "Symbol",
        "name_col": "Security",
        "sector_col": "GICS Sector",
        "suffix": "",
    },
    "nasdaq100": {
        "url": "https://en.wikipedia.org/wiki/NASDAQ-100",
        "table_idx": 5,  # Ticker, Company, ICB Industry, ICB Subsector
        "ticker_col": "Ticker",
        "name_col": "Company",
        "sector_col": "ICB Industry[15]",
        "suffix": "",
    },
    "hsi": {
        "url": "https://en.wikipedia.org/wiki/Hang_Seng_Index",
        "table_idx": 6,
        "ticker_col": "Ticker",
        "name_col": "Name",
        "sector_col": None,
        "suffix": ".HK",
    },
}


def fetch_index_constituents(index_name: str) -> pd.DataFrame:
    """Fetch index constituents from Wikipedia."""
    config = WIKI_TABLES[index_name]
    url = config["url"]

    print(f"[{index_name}] Fetching from Wikipedia...")
    html_content = _fetch_url(url)
    tables = pd.read_html(io.StringIO(html_content))

    if config["table_idx"] is not None:
        df = tables[config["table_idx"]]
    else:
        # Find the table that contains the ticker column
        found = False
        for i, table in enumerate(tables):
            if config["ticker_col"] in table.columns.tolist():
                df = table
                print(f"[{index_name}] Found table at index {i} ({len(df)} rows)")
                found = True
                break
        if not found:
            print(f"[{index_name}] Table structure changed. Available tables:")
            for i, t in enumerate(tables):
                print(f"  [{i}] {t.columns.tolist()} ({len(t)} rows)")
            return pd.DataFrame()

    # Clean up column names
    df.columns = df.columns.str.strip()

    result = pd.DataFrame()
    result["ticker"] = df[config["ticker_col"]].str.strip()

    # Clean ticker: remove SEHK: prefix and other noise
    result["ticker"] = result["ticker"].str.replace("SEHK:", "").str.replace("SEHK", "")
    result["ticker"] = result["ticker"].str.strip().str.replace("\xa0", " ").str.strip()
    result["name"] = df[config["name_col"]].str.strip()

    if config["sector_col"] and config["sector_col"] in df.columns:
        result["sector"] = df[config["sector_col"]].str.strip()

    # Add suffix (e.g. .HK for Hang Seng)
    if config["suffix"]:
        result["ticker"] = result["ticker"] + config["suffix"]

    # Drop duplicates and empty tickers
    result = result.drop_duplicates(subset="ticker").dropna(subset="ticker").reset_index(drop=True)

    print(f"[{index_name}] Total: {len(result)} stocks")
    return result


def fetch_prices(tickers: list, period: str = "5d") -> pd.DataFrame:
    """Fetch latest prices using yfinance."""
    import yfinance as yf

    print(f"Fetching prices for {len(tickers)} tickers...")
    results = []
    for i, ticker in enumerate(tickers):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period=period)
            if not hist.empty:
                last_close = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else last_close
                change_pct = round((last_close - prev_close) / prev_close * 100, 2) if prev_close else None
                results.append({
                    "ticker": ticker,
                    "price": round(last_close, 3),
                    "change_pct": change_pct,
                })
        except Exception as e:
            print(f"  Error fetching {ticker}: {e}")
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(tickers)}")

    return pd.DataFrame(results)


def main():
    all_data = {}

    # Fetch constituents from Wikipedia
    for index_name in WIKI_TABLES:
        df = fetch_index_constituents(index_name)
        if not df.empty:
            all_data[index_name] = df
            # Save to CSV
            csv_path = f"{index_name.lower()}_constituents.csv"
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"[{index_name}] Saved to {csv_path}")

    # Print summary
    print("\n=== Summary ===")
    for name, df in all_data.items():
        print(f"{name}: {len(df)} stocks")
        if not df.empty:
            print(f"  Sample: {df.iloc[0]['ticker']} - {df.iloc[0]['name']}")


if __name__ == "__main__":
    main()
