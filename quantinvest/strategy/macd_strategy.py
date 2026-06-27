"""MACD strategy."""

from __future__ import annotations

from typing import Any

import numpy as np

from quantinvest.strategy.base_strategy import BaseStrategy


class MACDStrategy(BaseStrategy):
    """MACD signal-line crossover with optional RSI filter.

    Uses pre-computed talib MACD/RSI arrays.

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
        rsi_overbought=70, rsi_oversold=30, _talib={},
    )

    @classmethod
    def needs_talib(cls, kwargs: dict) -> dict[str, Any]:
        rsi_p = kwargs.get("rsi_period", 0)
        return {
            "macd_fast": kwargs.get("fast", 12),
            "macd_slow": kwargs.get("slow", 26),
            "macd_signal_period": kwargs.get("signal", 9),
            "rsi_periods": [rsi_p] if rsi_p > 0 else [],
        }

    def next(self) -> None:
        super().next()
        idx = len(self.data.close) - 1
        t = self.p._talib

        macd_v = t["macd"][idx]
        sig_v = t["macd_signal"][idx]
        macd_prev = t["macd"][idx - 1]
        sig_prev = t["macd_signal"][idx - 1]
        cross = (macd_v - sig_v) - (macd_prev - sig_prev)

        rsi_ok = True
        if self.p.rsi_period > 0:
            rsi_val = t[f"rsi_{self.p.rsi_period}"][idx]
            if np.isnan(rsi_val):
                rsi_ok = False
            else:
                if not self.position and cross > 0:
                    rsi_ok = rsi_val < self.p.rsi_overbought
                elif self.position and cross < 0:
                    rsi_ok = rsi_val > self.p.rsi_oversold

        if not self.position:
            if cross > 0 and rsi_ok:
                self.buy()
        elif cross < 0 and rsi_ok:
            self.close()
