"""Multi-factor Alpha strategy.

Combines several technical factors into a composite score.
Buys when the alpha score crosses above a threshold,
sells when it drops below.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from quantinvest.strategy.base_strategy import BaseStrategy


class AlphaStrategy(BaseStrategy):
    """Multi-factor alpha strategy based on indicator resonance.

    Uses pre-computed talib ROC/SMA/RSI/BollingerBands arrays.

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
        momentum_period=10, trend_period=20, rsi_period=14,
        bb_period=20, bb_devfactor=2.0,
        momentum_weight=0.3, trend_weight=0.25,
        rsi_weight=0.25, bb_weight=0.2,
        buy_threshold=-10, sell_threshold=30, _talib={},
    )

    @classmethod
    def needs_talib(cls, kwargs: dict) -> dict[str, Any]:
        return {
            "sma_periods": [kwargs.get("trend_period", 20)],
            "rsi_periods": [kwargs.get("rsi_period", 14)],
            "roc_periods": [kwargs.get("momentum_period", 10)],
            "bb_period": kwargs.get("bb_period", 20),
            "bb_devfactor": kwargs.get("bb_devfactor", 2.0),
        }

    def _alpha_score(self, idx: int) -> float:
        t = self.p._talib
        close = t["_close"][idx]
        roc_val = t[f"roc_{self.p.momentum_period}"][idx]
        mom = roc_val if np.isfinite(roc_val) else 0.0

        sma_val = t[f"sma_{self.p.trend_period}"][idx]
        trend = 100 if close > sma_val else -100

        rsi_val = t[f"rsi_{self.p.rsi_period}"][idx]
        rsi_score = (50 - rsi_val) * 2 if np.isfinite(rsi_val) else 0.0

        bb_top = t["bb_upper"][idx]
        bb_bot = t["bb_lower"][idx]
        bb_width = bb_top - bb_bot
        if np.isfinite(bb_width) and bb_width > 0:
            bb_pos = (bb_top - close) / bb_width
        else:
            bb_pos = 0.5
        bb_score = bb_pos * 200 - 100

        return (
            self.p.momentum_weight * mom
            + self.p.trend_weight * trend
            + self.p.rsi_weight * rsi_score
            + self.p.bb_weight * bb_score
        )

    def next(self) -> None:
        super().next()
        idx = len(self.data.close) - 1
        score = self._alpha_score(idx)

        if not self.position:
            if score > self.p.buy_threshold:
                self.buy()
        elif score < self.p.sell_threshold:
            self.close()
