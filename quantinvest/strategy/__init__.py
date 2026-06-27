"""Strategy library for quantitative investing."""

from .ma_cross import MACrossStrategy
from .macd_strategy import MACDStrategy
from .bollinger import BollingerStrategy
from .turtle import TurtleStrategy
from .alpha import AlphaStrategy
from .reversal import ReversalStrategy
from .breakout import BreakoutStrategy
from .cost_cross import CostCrossStrategy
from .base_strategy import BaseStrategy

__all__ = [
    "MACrossStrategy",
    "MACDStrategy",
    "BollingerStrategy",
    "TurtleStrategy",
    "AlphaStrategy",
    "ReversalStrategy",
    "BreakoutStrategy",
    "CostCrossStrategy",
    "BaseStrategy",
]
