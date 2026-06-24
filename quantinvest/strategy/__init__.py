"""Strategy library for quantitative investing."""

from .ma_cross import MACrossStrategy
from .macd_strategy import MACDStrategy
from .bollinger import BollingerStrategy
from .base_strategy import BaseStrategy

__all__ = [
    "MACrossStrategy",
    "MACDStrategy",
    "BollingerStrategy",
    "BaseStrategy",
]
