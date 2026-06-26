"""Reversal strategy based on MACD divergence and RSI extremes.

Detects bullish/bearish divergence between price and MACD histogram,
combined with RSI overbought/oversold confirmation.
"""

from __future__ import annotations

import backtrader as bt

from quantinvest.strategy.base_strategy import BaseStrategy


class ReversalStrategy(BaseStrategy):
    """Reversal strategy using MACD divergence + RSI extremes.

    Bullish reversal: price makes lower low but MACD histogram makes higher low,
    confirmed by RSI crossing above oversold threshold.
    Bearish reversal: price makes higher high but MACD histogram makes lower high,
    confirmed by RSI crossing below overbought threshold.

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
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        rsi_period=14,
        divergence_lookback=5,
        rsi_oversold=30,
        rsi_overbought=70,
    )

    def __init__(self) -> None:
        super().__init__()
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal,
        )
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)

    def _bullish_divergence(self) -> bool:
        """Check if price made lower low while MACD histogram made higher low."""
        lb = self.p.divergence_lookback
        if len(self.data.close) < lb + 1:
            return False
        # Price lower low: current close < close lb bars ago
        price_lower = self.data.close[0] < self.data.close[-lb]
        # MACD histogram = macd - signal; higher low means less negative / more positive
        hist_0 = self.macd.macd[0] - self.macd.signal[0]
        hist_lb = self.macd.macd[-lb] - self.macd.signal[-lb]
        macd_higher = hist_0 > hist_lb
        # RSI confirmation: RSI just crossed above oversold
        rsi_confirm = self.rsi[0] > self.p.rsi_oversold and self.rsi[-1] <= self.p.rsi_oversold
        return price_lower and macd_higher and rsi_confirm

    def _bearish_divergence(self) -> bool:
        """Check if price made higher high while MACD histogram made lower high."""
        lb = self.p.divergence_lookback
        if len(self.data.close) < lb + 1:
            return False
        # Price higher high: current close > close lb bars ago
        price_higher = self.data.close[0] > self.data.close[-lb]
        # MACD histogram lower high
        hist_0 = self.macd.macd[0] - self.macd.signal[0]
        hist_lb = self.macd.macd[-lb] - self.macd.signal[-lb]
        macd_lower = hist_0 < hist_lb
        # RSI confirmation: RSI just crossed below overbought
        rsi_confirm = self.rsi[0] < self.p.rsi_overbought and self.rsi[-1] >= self.p.rsi_overbought
        return price_higher and macd_lower and rsi_confirm

    def next(self) -> None:
        super().next()
        if not self.position:
            if self._bullish_divergence():
                self.buy()
        elif self._bearish_divergence():
            self.close()
