"""Breakout strategy based on support and resistance levels.

Identifies support/resistance from recent price extremes,
enters on breakout above resistance, exits on breakdown below support.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from quantinvest.strategy.base_strategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """Support/Resistance breakout strategy.

    Uses pre-computed talib Highest/Lowest/SMA(volume) arrays.

    Params:
        lookback (int): Lookback period for support/resistance (default 20)
        breakout_threshold (float): Minimum breakout percentage (default 0.01 = 1%)
        use_volume_filter (bool): Require volume > average on breakout (default True)
        volume_factor (float): Volume must exceed this * average (default 1.2)
    """

    params = dict(
        lookback=20, breakout_threshold=0.01,
        use_volume_filter=True, volume_factor=1.2, _talib={},
    )

    @classmethod
    def needs_talib(cls, kwargs: dict) -> dict[str, Any]:
        vol_sma = [kwargs.get("lookback", 20)] if kwargs.get("use_volume_filter", True) else []
        return {
            "highest_periods": [kwargs.get("lookback", 20)],
            "lowest_periods": [kwargs.get("lookback", 20)],
            "vol_sma_periods": vol_sma,
        }

    def _breakout_above_resistance(self, idx: int) -> bool:
        t = self.p._talib
        resist = t[f"highest_{self.p.lookback}"][idx]
        if not np.isfinite(resist):
            return False
        close = t["_close"][idx]
        breakout_pct = (close - resist) / resist
        if breakout_pct < self.p.breakout_threshold:
            return False

        if self.p.use_volume_filter:
            vol_avg = t[f"vol_sma_{self.p.lookback}"][idx]
            if np.isfinite(vol_avg) and vol_avg > 0:
                if t["_volume"][idx] < self.p.volume_factor * vol_avg:
                    return False

        return True

    def _breakdown_below_support(self, idx: int) -> bool:
        t = self.p._talib
        sup = t[f"lowest_{self.p.lookback}"][idx]
        if not np.isfinite(sup):
            return False
        close = t["_close"][idx]
        return (close - sup) / sup < -self.p.breakout_threshold

    def next(self) -> None:
        super().next()
        idx = len(self.data.close) - 1
        if not self.position:
            if self._breakout_above_resistance(idx):
                self.buy()
        elif self._breakdown_below_support(idx):
            self.close()
