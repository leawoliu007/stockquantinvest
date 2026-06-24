"""Visualization helpers for quantitative investing."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd


def _format_date(ax: plt.Axes) -> None:
    """Format x-axis as date."""
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.tick_params(axis="x", rotation=45)


def compute_indicators(df: pd.DataFrame, strategy: str = "macd", **kwargs) -> dict[str, pd.Series]:
    """Compute common indicators for plotting.

    Args:
        df: DataFrame with columns date, open, high, low, close, volume
        strategy: one of 'ma', 'macd', 'bollinger'
        **kwargs: passed to indicator computation

    Returns:
        dict of {name: Series} ready for plotting
    """
    close = df["close"]

    if strategy == "ma":
        fast = kwargs.get("fast", 5)
        slow = kwargs.get("slow", 20)
        return {
            f"MA{fast}": close.rolling(fast).mean(),
            f"MA{slow}": close.rolling(slow).mean(),
        }

    if strategy == "macd":
        fast = kwargs.get("fast", 12)
        slow = kwargs.get("slow", 26)
        signal = kwargs.get("signal", 9)
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {
            "MACD": macd_line,
            "Signal": signal_line,
            "Histogram": histogram,
        }

    if strategy == "bollinger":
        period = kwargs.get("period", 20)
        devfactor = kwargs.get("devfactor", 2.0)
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = sma + devfactor * std
        lower = sma - devfactor * std
        return {
            "Bollinger Upper": upper,
            "Bollinger Middle": sma,
            "Bollinger Lower": lower,
        }

    raise ValueError(f"Unknown strategy: {strategy}")


def _extract_series(series) -> np.ndarray:
    """Extract numpy array from backtrader indicator or pandas Series."""
    if hasattr(series, "lines"):
        return np.asarray(series.lines[0].array)
    elif hasattr(series, "__len__"):
        if len(series) == 1:
            return None
        return np.asarray(series).flatten()
    else:
        return np.asarray(series)


def _is_macd_indicator(name: str) -> bool:
    """Check if an indicator belongs in a MACD subplot."""
    return name.lower().startswith("macd") or name.lower() == "signal" or name.lower() == "histogram"


def plot_kline(
    df: pd.DataFrame,
    title: str = "K-Line Chart",
    indicators: dict | None = None,
    output: str | Path | None = None,
) -> None:
    """Plot OHLC candlestick with optional indicator overlays.

    Args:
        df: DataFrame with columns date, open, high, low, close, volume
        title: Chart title
        indicators: dict of {name: Series} to overlay on chart
        output: File path to save figure (default: show inline)
    """
    # Separate MACD indicators from price indicators
    price_indicators = {}
    macd_indicators = {}
    if indicators:
        for name, series in indicators.items():
            if _is_macd_indicator(name):
                macd_indicators[name] = series
            else:
                price_indicators[name] = series

    # Determine number of subplots based on which indicators are present
    if macd_indicators and price_indicators:
        n_subplots = 3
        height_ratios = [4, 1, 2]
    elif macd_indicators:
        n_subplots = 3
        height_ratios = [4, 1, 2]
    else:
        n_subplots = 2
        height_ratios = [3, 1]

    fig, axes = plt.subplots(n_subplots, 1, figsize=(14, 8), gridspec_kw={"height_ratios": height_ratios})

    # --- Price chart (close + MA lines) ---
    ax1 = axes[0]
    x_vals = mdates.date2num(df.index)
    colors = ["#26a69a" if c >= o else "#ef5350" for o, c in zip(df["open"], df["close"])]

    # Close line with colored area fill
    ax1.plot(x_vals, df["close"], color="#2962ff", linewidth=1.5, label="Close")
    ax1.fill_between(x_vals, df["close"].values, alpha=0.1, color="#2962ff")

    if price_indicators:
        for name, series in price_indicators.items():
            values = _extract_series(series)
            if values is not None:
                ax1.plot(x_vals, values, linewidth=1, label=name)

    ax1.set_title(title)
    ax1.legend()
    ax1.grid(True)
    _format_date(ax1)

    # --- Volume bar (middle subplot) ---
    ax2 = axes[1]
    vol_colors = ["#26a69a" if c >= o else "#ef5350" for o, c in zip(df["open"], df["close"])]
    ax2.bar(df.index, df["volume"], color=vol_colors, alpha=0.7)
    ax2.set_xlabel("Date")
    ax2.grid(True)
    _format_date(ax2)

    # --- MACD subplot (bottom) ---
    if macd_indicators:
        ax3 = axes[2]
        for name, series in macd_indicators.items():
            values = _extract_series(series)
            if values is not None:
                linestyle = "--" if "signal" in name.lower() else "-"
                ax3.plot(df.index, values, linewidth=1.5, label=name, linestyle=linestyle)

        # Plot zero line first so it appears behind
        ax3.axhline(0, color="gray", linewidth=0.8, linestyle="-")
        ax3.set_title("MACD")
        ax3.legend()
        ax3.grid(True)
        _format_date(ax3)

    fig.tight_layout()
    if output:
        fig.savefig(output, dpi=150)
        print(f"Chart saved to {output}")
    else:
        plt.show()


def plot_equity_curve(
    equity: pd.Series,
    title: str = "Equity Curve",
    output: str | Path | None = None,
) -> None:
    """Plot cumulative equity curve."""
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(equity.index, equity.values, linewidth=1.5, color="#2962ff")
    ax.fill_between(equity.index, equity.values, alpha=0.3)
    ax.set_title(title)
    ax.grid(True)
    _format_date(ax)
    fig.tight_layout()
    if output:
        fig.savefig(output, dpi=150)
        print(f"Chart saved to {output}")
    else:
        plt.show()
