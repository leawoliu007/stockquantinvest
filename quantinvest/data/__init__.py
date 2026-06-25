"""Unified data interface for quantitative investing."""

from .akshare_data import AkShareData
from .baostock_data import BaoStockData
from .yfinance_data import YFinanceData
from .base import QuantData, StockData
from .database import QuantDB

__all__ = [
    "QuantData",
    "StockData",
    "AkShareData",
    "BaoStockData",
    "YFinanceData",
    "QuantDB",
]
