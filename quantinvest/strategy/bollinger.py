"""Bollinger Bands strategy."""

from __future__ import annotations

import backtrader as bt

from quantinvest.strategy.base_strategy import BaseStrategy


class BollingerStrategy(BaseStrategy):
    """Buy at lower band, sell at upper band.

    Params:
        period (int): Lookback (default 20)
        devfactor (float): Deviation multiplier (default 2.0)
    """

    params = dict(period=20, devfactor=2.0)

    def __init__(self) -> None:
        super().__init__()
        self.bb = bt.indicators.BollingerBands(
            self.data.close,
            period=self.p.period,
            devfactor=self.p.devfactor,
        )

    def next(self) -> None:
        super().next()
        if not self.position:
            if self.data.close[0] < self.bb.bot[0]:
                self.buy()
        elif self.data.close[0] > self.bb.top[0]:
            self.close()
