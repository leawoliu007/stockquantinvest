"""Moving average crossover strategy."""

from __future__ import annotations

from typing import Any

from quantinvest.strategy.base_strategy import BaseStrategy


class MACrossStrategy(BaseStrategy):
    """Simple moving average crossover.

    Uses pre-computed talib SMA arrays (computed once before backtest).

    Params:
        short (int): Short MA period (default 5)
        long (int): Long MA period (default 20)
    """

    params = dict(short=5, long=20, _talib={})

    @classmethod
    def needs_talib(cls, kwargs: dict) -> dict[str, Any]:
        return {"sma_periods": [kwargs.get("short", 5), kwargs.get("long", 20)]}

    def next(self) -> None:
        super().next()
        idx = len(self.data.close) - 1
        t = self.p._talib
        sma_s = t[f"sma_{self.p.short}"][idx]
        sma_l = t[f"sma_{self.p.long}"][idx]
        prev_s = t[f"sma_{self.p.short}"][idx - 1]
        prev_l = t[f"sma_{self.p.long}"][idx - 1]

        cross = (sma_s - sma_l) - (prev_s - prev_l)
        if not self.position:
            if cross > 0:
                self.buy()
        elif cross < 0:
            self.close()
