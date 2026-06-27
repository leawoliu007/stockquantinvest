"""Bollinger Bands strategy."""

from __future__ import annotations

from typing import Any

import numpy as np

from quantinvest.strategy.base_strategy import BaseStrategy


class BollingerStrategy(BaseStrategy):
    """Buy at lower band, sell at upper band.

    Uses pre-computed talib BBANDS arrays.

    Params:
        period (int): Lookback (default 20)
        devfactor (float): Deviation multiplier (default 2.0)
    """

    params = dict(period=20, devfactor=2.0, _talib={})

    @classmethod
    def needs_talib(cls, kwargs: dict) -> dict[str, Any]:
        return {
            "bb_period": kwargs.get("period", 20),
            "bb_devfactor": kwargs.get("devfactor", 2.0),
        }

    def next(self) -> None:
        super().next()
        idx = len(self.data.close) - 1
        t = self.p._talib
        c = float(self.data.close[0])
        top = t["bb_upper"][idx]
        bot = t["bb_lower"][idx]
        if not np.isfinite(top) or not np.isfinite(bot):
            return
        if not self.position:
            if c < bot:
                self.buy()
        elif c > top:
            self.close()
