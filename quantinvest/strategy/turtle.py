"""Turtle Trading strategy (System 1).

Entry: price breaks above 20-day high
Exit: price breaks below 10-day low
Position sizing based on ATR(10)
"""

from __future__ import annotations

from typing import Any

import numpy as np

from quantinvest.strategy.base_strategy import BaseStrategy


class TurtleStrategy(BaseStrategy):
    """Classic Turtle Trading System 1.

    Uses pre-computed talib ATR/Highest/Lowest arrays.

    Params:
        entry_period (int): Breakout entry lookback (default 20)
        exit_period (int): Breakout exit lookback (default 10)
        atr_period (int): ATR period for sizing (default 10)
        risk_pct (float): Risk per trade as fraction of value (default 0.01)
    """

    params = dict(entry_period=20, exit_period=10, atr_period=10, risk_pct=0.01, _talib={})

    @classmethod
    def needs_talib(cls, kwargs: dict) -> dict[str, Any]:
        return {
            "atr_period": kwargs.get("atr_period", 10),
            "highest_periods": [kwargs.get("entry_period", 20)],
            "lowest_periods": [kwargs.get("exit_period", 10)],
        }

    def next(self) -> None:
        super().next()
        idx = len(self.data.close) - 1
        t = self.p._talib
        c = float(self.data.close[0])
        highest_val = t[f"highest_{self.p.entry_period}"][idx]
        lowest_val = t[f"lowest_{self.p.exit_period}"][idx]
        if not np.isfinite(highest_val) or not np.isfinite(lowest_val):
            return
        if not self.position:
            if c > highest_val:
                self.buy()
        else:
            if c < lowest_val:
                self.close()
