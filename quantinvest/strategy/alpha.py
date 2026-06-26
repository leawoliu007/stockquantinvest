"""Multi-factor Alpha strategy.

Combines several technical factors into a composite score.
Buys when the alpha score crosses above a threshold,
sells when it drops below.
"""

from __future__ import annotations

import backtrader as bt

from quantinvest.strategy.base_strategy import BaseStrategy


class AlphaStrategy(BaseStrategy):
    """Multi-factor alpha strategy based on indicator resonance.

    Factors:
      - Momentum: ROC (Rate of Change) over momentum_period
      - Trend: price vs SMA(trend_period), positive when above
      - Mean Reversion: RSI oversold/overbought zones
      - Volatility: Bollinger Band position (normalized 0-1)

    Composite score = weighted sum, range roughly [-100, 100].
    Buy when score crosses above buy_threshold.
    Sell when score crosses below sell_threshold.

    Params:
        momentum_period (int): ROC lookback (default 10)
        trend_period (int): SMA for trend filter (default 20)
        rsi_period (int): RSI lookback (default 14)
        bb_period (int): Bollinger Bands period (default 20)
        bb_devfactor (float): Bollinger deviation factor (default 2.0)
        momentum_weight (float): Momentum weight (default 0.3)
        trend_weight (float): Trend weight (default 0.25)
        rsi_weight (float): RSI weight (default 0.25)
        bb_weight (float): BB position weight (default 0.2)
        buy_threshold (float): Score threshold to enter (default -10)
        sell_threshold (float): Score threshold to exit (default 30)
    """

    params = dict(
        momentum_period=10,
        trend_period=20,
        rsi_period=14,
        bb_period=20,
        bb_devfactor=2.0,
        momentum_weight=0.3,
        trend_weight=0.25,
        rsi_weight=0.25,
        bb_weight=0.2,
        buy_threshold=-10,
        sell_threshold=30,
    )

    def __init__(self) -> None:
        super().__init__()
        # Momentum factor: ROC normalized to [-100, 100] roughly
        self.roc = bt.indicators.ROC(
            self.data.close, period=self.p.momentum_period
        )

        # Trend factor: distance from SMA, normalized by price
        self.sma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.p.trend_period
        )

        # RSI factor: map RSI(0-100) to score(-100 to 100), neutral at 50
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)

        # Bollinger Band position: (close - bot) / (top - bot) -> [0, 1]
        self.bb = bt.indicators.BollingerBands(
            self.data.close,
            period=self.p.bb_period,
            devfactor=self.p.bb_devfactor,
        )

    def _alpha_score(self) -> float:
        """Compute composite alpha score."""
        # Momentum: ROC value directly (percentage change * 10)
        mom = self.roc[0] * 10

        # Trend: positive when price above SMA
        trend = 100 if self.data.close[0] > self.sma[0] else -100

        # RSI: map [0, 100] -> [-100, 100], neutral at 50
        rsi_score = (50 - self.rsi[0]) * 2

        # BB position: low position (near bottom) is bullish
        bb_width = self.bb.top[0] - self.bb.bot[0]
        if bb_width > 0:
            bb_pos = (self.bb.top[0] - self.data.close[0]) / bb_width
        else:
            bb_pos = 0.5
        bb_score = bb_pos * 200 - 100

        score = (
            self.p.momentum_weight * mom
            + self.p.trend_weight * trend
            + self.p.rsi_weight * rsi_score
            + self.p.bb_weight * bb_score
        )
        return score

    def next(self) -> None:
        super().next()
        score = self._alpha_score()

        if not self.position:
            if score > self.p.buy_threshold:
                self.buy()
        elif score < self.p.sell_threshold:
            self.close()
