"""MACD strategy."""

from __future__ import annotations

import backtrader as bt

from quantinvest.strategy.base_strategy import BaseStrategy


class MACDStrategy(BaseStrategy):
    """MACD signal-line crossover with optional RSI filter.

    Params:
        fast (int): Fast EMA period (default 12)
        slow (int): Slow EMA period (default 26)
        signal (int): Signal EMA period (default 9)
        rsi_period (int): RSI lookback for filter (0 = disabled)
        rsi_overbought (float): RSI overbought threshold
        rsi_oversold (float): RSI oversold threshold
    """

    params = dict(
        fast=12, slow=26, signal=9, rsi_period=0,
        rsi_overbought=70, rsi_oversold=30,
    )

    def __init__(self) -> None:
        super().__init__()
        self.macd = bt.indicators.MACD(self.data.close,
                                       period_me1=self.p.fast,
                                       period_me2=self.p.slow,
                                       period_signal=self.p.signal)
        self.cross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

        if self.p.rsi_period > 0:
            self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)
        else:
            self.rsi = None

    def next(self) -> None:
        super().next()
        if not self.position:
            if self.cross > 0 and (self.rsi is None or self.rsi < self.p.rsi_overbought):
                self.buy()
        elif self.cross < 0 and (self.rsi is None or self.rsi > self.p.rsi_oversold):
            self.close()
