"""Reversal strategy based on MACD divergence and RSI extremes.

Detects bullish/bearish divergence between price and MACD histogram,
combined with RSI overbought/oversold confirmation.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from quantinvest.strategy.base_strategy import BaseStrategy


class ReversalStrategy(BaseStrategy):
    """Reversal strategy using MACD divergence + RSI extremes.

    Uses pre-computed talib MACD/RSI arrays.

    Params:
        macd_fast (int): MACD fast EMA period (default 12)
        macd_slow (int): MACD slow EMA period (default 26)
        macd_signal (int): MACD signal period (default 9)
        rsi_period (int): RSI lookback (default 14)
        divergence_lookback (int): Bars to scan for divergence peaks (default 5)
        rsi_oversold (float): RSI oversold threshold (default 30)
        rsi_overbought (float): RSI overbought threshold (default 70)
    """

    params = dict(
        macd_fast=12, macd_slow=26, macd_signal=9,
        rsi_period=14, divergence_lookback=5,
        rsi_oversold=30, rsi_overbought=70, _talib={},
    )

    @classmethod
    def needs_talib(cls, kwargs: dict) -> dict[str, Any]:
        return {
            "macd_fast": kwargs.get("macd_fast", 12),
            "macd_slow": kwargs.get("macd_slow", 26),
            "macd_signal_period": kwargs.get("macd_signal", 9),
            "rsi_periods": [kwargs.get("rsi_period", 14)],
        }

    def _bullish_divergence(self, idx: int) -> bool:
        lb = self.p.divergence_lookback
        lb_idx = idx - lb
        if lb_idx < 0:
            return False
        t = self.p._talib
        close_arr = t["_close"]

        # Price lower low
        price_lower = close_arr[idx] < close_arr[lb_idx]

        # MACD histogram higher low
        hist_0 = t["macd_hist"][idx]
        hist_lb = t["macd_hist"][lb_idx]
        if not np.isfinite(hist_0) or not np.isfinite(hist_lb):
            return False

        # RSI confirmation
        rsi_arr = t[f"rsi_{self.p.rsi_period}"]
        rsi_0 = rsi_arr[idx]
        rsi_prev = rsi_arr[idx - 1]
        if not np.isfinite(rsi_0) or not np.isfinite(rsi_prev):
            return False
        rsi_confirm = rsi_0 > self.p.rsi_oversold and rsi_prev <= self.p.rsi_oversold

        return price_lower and hist_0 > hist_lb and rsi_confirm

    def _bearish_divergence(self, idx: int) -> bool:
        lb = self.p.divergence_lookback
        lb_idx = idx - lb
        if lb_idx < 0:
            return False
        t = self.p._talib
        close_arr = t["_close"]

        price_higher = close_arr[idx] > close_arr[lb_idx]

        hist_0 = t["macd_hist"][idx]
        hist_lb = t["macd_hist"][lb_idx]
        if not np.isfinite(hist_0) or not np.isfinite(hist_lb):
            return False

        rsi_arr = t[f"rsi_{self.p.rsi_period}"]
        rsi_0 = rsi_arr[idx]
        rsi_prev = rsi_arr[idx - 1]
        if not np.isfinite(rsi_0) or not np.isfinite(rsi_prev):
            return False
        rsi_confirm = rsi_0 < self.p.rsi_overbought and rsi_prev >= self.p.rsi_overbought

        return price_higher and hist_0 < hist_lb and rsi_confirm

    def next(self) -> None:
        super().next()
        idx = len(self.data.close) - 1
        if not self.position:
            if self._bullish_divergence(idx):
                self.buy()
        elif self._bearish_divergence(idx):
            self.close()
