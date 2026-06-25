from __future__ import annotations

import abc
from datetime import date

import pandas as pd


class StockData(abc.ABC):
    """Abstract base class for market data providers."""

    @abc.abstractmethod
    def fetch(
        self,
        symbol: str,
        start: str | date = "2020-01-01",
        end: str | date = date.today().strftime("%Y-%m-%d"),
        freq: str = "daily",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data.

        Returns a DataFrame with columns:
            date, open, high, low, close, volume, [optional indicators]

        Args:
            freq: Frequency — "daily", "weekly", "monthly", "30min", "15min", "5min"
            use_cache: If True, use SQLite cache for incremental updates.
        """

    @abc.abstractmethod
    def fetch_realtime(self, symbol: str) -> pd.DataFrame:
        """Fetch real-time (or most recent) quote."""


class QuantData:
    """Factory that auto-selects the best data source for a given symbol."""

    _SOURCE_MAP = {
        ".SH": "akshare",
        ".SZ": "akshare",
        ".ETF": "akshare",
        ".HK": "yfinance",
        ".US": "yfinance",
    }

    @classmethod
    def _infer_source(cls, symbol: str) -> type[StockData]:
        for suffix, source in cls._SOURCE_MAP.items():
            if symbol.endswith(suffix):
                break
        else:
            # Default to yfinance for US stocks and others
            source = "yfinance"

        from .akshare_data import AkShareData
        from .baostock_data import BaoStockData
        from .yfinance_data import YFinanceData

        return {
            "akshare": AkShareData,
            "baostock": BaoStockData,
            "yfinance": YFinanceData,
        }[source]

    @classmethod
    def get(cls, symbol: str) -> StockData:
        """Return a data provider instance for *symbol*."""
        source = cls._infer_source(symbol)
        return source()
