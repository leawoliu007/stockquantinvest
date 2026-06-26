"""Turtle Trading strategy (System 1).

Entry: price breaks above 20-day high
Exit: price breaks below 10-day low
Position sizing based on ATR(10)
"""

from __future__ import annotations

import backtrader as bt

from quantinvest.strategy.base_strategy import BaseStrategy


class TurtleStrategy(BaseStrategy):
    """Classic Turtle Trading System 1.

    Params:
        entry_period (int): Breakout entry lookback (default 20)
        exit_period (int): Breakout exit lookback (default 10)
        atr_period (int): ATR period for sizing (default 10)
        risk_pct (float): Risk per trade as fraction of value (default 0.01)
    """

    params = dict(entry_period=20, exit_period=10, atr_period=10, risk_pct=0.01)

    def __init__(self) -> None:
        super().__init__()
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.highest = bt.indicators.Highest(
            self.data.high, period=self.p.entry_period
        )
        self.lowest = bt.indicators.Lowest(
            self.data.low, period=self.p.exit_period
        )

    def next(self) -> None:
        super().next()
        if not self.position:
            # Entry: close breaks above highest high of entry_period
            if self.data.close[0] > self.highest[-1]:
                self.buy()
        else:
            # Exit: close breaks below lowest low of exit_period
            if self.data.close[0] < self.lowest[-1]:
                self.close()
