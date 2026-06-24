from __future__ import annotations

import datetime as dt
import os

import yfinance as yf

from ..config import load_config


class YFinanceData:
    """Fetch US / HK stock data from Yahoo Finance."""

    def __init__(self) -> None:
        """Apply proxy settings once at initialization."""
        cfg = load_config()
        if cfg.https_proxy:
            os.environ["HTTPS_PROXY"] = cfg.https_proxy
        if cfg.http_proxy:
            os.environ["HTTP_PROXY"] = cfg.http_proxy

    def fetch(
        self,
        symbol: str,
        start: str | dt.date = "2020-01-01",
        end: str | dt.date = dt.date.today().strftime("%Y-%m-%d"),
        freq: str = "daily",
    ) -> pd.DataFrame:
        ticker = self._to_yf_symbol(symbol)
        df = yf.Ticker(ticker).history(
            start=str(start), end=str(end), interval="1d"
        )
        return self._clean(df)

    def fetch_realtime(self, symbol: str) -> pd.DataFrame:
        ticker = self._to_yf_symbol(symbol)
        df = yf.Ticker(ticker).history(period="1d")
        return self._clean(df)

    @staticmethod
    def _to_yf_symbol(symbol: str) -> str:
        """Convert QuantInvest symbol to Yahoo Finance ticker.

        Strips the .US suffix for US stocks; leaves other suffixes intact
        (e.g. 0700.HK stays as-is for Yahoo Finance).
        """
        if symbol.endswith(".US"):
            return symbol[:-3]
        return symbol

    @staticmethod
    def _clean(df: pd.DataFrame) -> pd.DataFrame:
        cols = ["Open", "High", "Low", "Close", "Volume"]
        rename_map = {c.lower(): c.lower() for c in cols}
        df = df[cols].copy()
        df.columns = list(rename_map.values())
        df.index.name = "date"
        return df.sort_index()
