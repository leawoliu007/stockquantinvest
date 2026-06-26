"""Breakout strategy based on support and resistance levels.

Identifies support/resistance from recent price extremes,
enters on breakout above resistance, exits on breakdown below support.
"""

from __future__ import annotations

import backtrader as bt

from quantinvest.strategy.base_strategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """Support/Resistance breakout strategy.

    Calculates dynamic support and resistance levels from recent price range.
    Enters long when price breaks above resistance with volume confirmation.
    Exits when price breaks below support.

    Params:
        lookback (int): Lookback period for support/resistance (default 20)
        breakout_threshold (float): Minimum breakout percentage (default 0.01 = 1%)
        use_volume_filter (bool): Require volume > average on breakout (default True)
        volume_factor (float): Volume must exceed this * average (default 1.2)
    """

    params = dict(
        lookback=20,
        breakout_threshold=0.01,
        use_volume_filter=True,
        volume_factor=1.2,
    )

    def __init__(self) -> None:
        super().__init__()
        # Dynamic support/resistance from recent price range
        self.resistance = bt.indicators.Highest(
            self.data.high, period=self.p.lookback
        )
        self.support = bt.indicators.Lowest(
            self.data.low, period=self.p.lookback
        )

        if self.p.use_volume_filter:
            self.vol_avg = bt.indicators.SimpleMovingAverage(
                self.data.volume, period=self.p.lookback
            )

    def _breakout_above_resistance(self) -> bool:
        """Check if price breaks above recent resistance with sufficient margin."""
        resist = self.resistance[-1]  # Resistance before current bar
        close = self.data.close[0]
        breakout_pct = (close - resist) / resist
        if breakout_pct < self.p.breakout_threshold:
            return False

        # Volume confirmation
        if self.p.use_volume_filter:
            vol_avg = self.vol_avg[0]
            if vol_avg > 0 and self.data.volume[0] < self.p.volume_factor * vol_avg:
                return False

        return True

    def _breakdown_below_support(self) -> bool:
        """Check if price breaks below recent support."""
        sup = self.support[-1]  # Support before current bar
        close = self.data.close[0]
        breakdown_pct = (close - sup) / sup
        return breakdown_pct < -self.p.breakout_threshold

    def next(self) -> None:
        super().next()
        if not self.position:
            if self._breakout_above_resistance():
                self.buy()
        elif self._breakdown_below_support():
            self.close()
