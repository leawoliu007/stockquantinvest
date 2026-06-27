"""Pre-compute talib indicators from OHLCV DataFrame.

Called by BacktestEngine before running the strategy. Returns a dict of
numpy arrays keyed by indicator name, which the strategy accesses by bar index.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import talib


def precompute(
    df: pd.DataFrame,
    *,
    sma_periods: list[int] | None = None,
    ema_periods: list[int] | None = None,
    macd_fast: int = 0,
    macd_slow: int = 0,
    macd_signal_period: int = 9,
    rsi_periods: list[int] | None = None,
    roc_periods: list[int] | None = None,
    atr_period: int | None = None,
    bb_period: int = 20,
    bb_devfactor: float = 2.0,
    highest_periods: list[int] | None = None,
    lowest_periods: list[int] | None = None,
    vol_sma_periods: list[int] | None = None,
) -> dict[str, Any]:
    """Compute all requested talib indicators on full OHLCV arrays.

    Returns a dict like:
        {"sma_5": array, "sma_20": array, "macd": array, ...}
    """
    close = df["close"].values.astype(np.float64)
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    volume = df["volume"].values.astype(np.float64) if "volume" in df.columns else None

    result: dict[str, Any] = {}
    result["_close"] = close  # expose close for strategies that need it
    result["_high"] = high
    result["_low"] = low
    if volume is not None:
        result["_volume"] = volume

    # SMA
    for p in sma_periods or []:
        result[f"sma_{p}"] = talib.SMA(close, timeperiod=p)

    # EMA
    for p in ema_periods or []:
        result[f"ema_{p}"] = talib.EMA(close, timeperiod=p)

    # MACD
    if macd_fast and macd_slow:
        m, s, h = talib.MACD(
            close, fastperiod=macd_fast, slowperiod=macd_slow,
            signalperiod=macd_signal_period,
        )
        result["macd"] = m
        result["macd_signal"] = s
        result["macd_hist"] = h

    # RSI
    for p in rsi_periods or []:
        result[f"rsi_{p}"] = talib.RSI(close, timeperiod=p)

    # ROC
    for p in roc_periods or []:
        result[f"roc_{p}"] = talib.ROC(close, timeperiod=p)

    # ATR
    if atr_period is not None:
        result[f"atr_{atr_period}"] = talib.ATR(high, low, close, timeperiod=atr_period)

    # Bollinger Bands
    u, mid, l = talib.BBANDS(
        close, timeperiod=bb_period, nbdevup=bb_devfactor, nbdevdn=bb_devfactor
    )
    result["bb_upper"] = u
    result["bb_mid"] = mid
    result["bb_lower"] = l

    # Highest / Lowest
    for p in highest_periods or []:
        result[f"highest_{p}"] = talib.MAX(high, timeperiod=p)

    for p in lowest_periods or []:
        result[f"lowest_{p}"] = talib.MIN(low, timeperiod=p)

    # Volume SMA
    if volume is not None:
        for p in vol_sma_periods or []:
            result[f"vol_sma_{p}"] = talib.SMA(volume, timeperiod=p)

    return result
