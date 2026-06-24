"""Moving average crossover strategy."""

from __future__ import annotations

import backtrader as bt

from quantinvest.strategy.base_strategy import BaseStrategy


class MACrossStrategy(BaseStrategy):
    """Simple moving average crossover.

    Params:
        short (int): Short MA period (default 5)
        long (int): Long MA period (default 20)
    """

    params = dict(short=5, long=20)

    def __init__(self) -> None:
        super().__init__()
        self.sma_short = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.p.short
        )
        self.sma_long = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.p.long
        )
        self.crossover = bt.indicators.CrossOver(self.sma_short, self.sma_long)

    def next(self) -> None:
        super().next()
        if not self.position:
            if self.crossover > 0:
                self.buy()
        elif self.crossover < 0:
            self.close()
