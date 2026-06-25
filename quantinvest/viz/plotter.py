"""Visualization helpers for quantitative investing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


def compute_indicators(df: pd.DataFrame, strategy: str = "macd", **kwargs: Any) -> dict[str, pd.Series]:
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


def _extract_series(series: Any) -> np.ndarray | None:
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
    trade_signals: pd.DataFrame | None = None,
    completed_trades: pd.DataFrame | None = None,
    output: str | Path | None = None,
) -> None:
    """Plot OHLC candlestick with optional indicator overlays and trade signals.

    Args:
        df: DataFrame with columns date, open, high, low, close, volume
        title: Chart title
        indicators: dict of {name: Series} to overlay on chart
        trade_signals: DataFrame with columns date, signal, price (optional, legacy)
        completed_trades: DataFrame with columns buy_date, sell_date, pnl, is_profitable (optional)
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

    # Plot trade fill regions if completed_trades provided
    if completed_trades is not None and not completed_trades.empty:
        from matplotlib.patches import Patch

        y_min = 0
        y_max = df["close"].max()

        for _, row in completed_trades.iterrows():
            buy_date = row["buy_date"]
            sell_date = row["sell_date"]
            is_profitable = row["is_profitable"]

            # Convert to datetime for comparison with DataFrame index
            buy_dt = pd.Timestamp(buy_date)
            sell_dt = pd.Timestamp(sell_date)

            # Handle timezone-aware index by converting to tz-naive if needed
            if df.index.tz is not None:
                buy_dt = buy_dt.tz_localize(df.index.tz)
                sell_dt = sell_dt.tz_localize(df.index.tz)

            # Draw transparent block from y=0 to y=max across the trade period
            x_start = mdates.date2num(buy_dt)
            x_end = mdates.date2num(sell_dt)
            color = "#ef5350" if is_profitable else "#26a69a"
            ax1.fill_between(
                [x_start, x_end],
                [y_min, y_min],
                [y_max, y_max],
                color=color,
                alpha=0.15,
                zorder=2,
            )

        # Build legend with trade region entries
        legend_elements = [
            Patch(color="#ef5350", alpha=0.15, label="Profit trade"),
            Patch(color="#26a69a", alpha=0.15, label="Loss trade"),
        ]
        existing_handles, existing_labels = ax1.get_legend_handles_labels()
        ax1.legend(
            handles=existing_handles + legend_elements,
            labels=existing_labels + [e.get_label() for e in legend_elements],
        )

        # Calculate and display win rate & profit/loss ratio
        total_trades = len(completed_trades)
        win_count = completed_trades["is_profitable"].sum()
        win_rate = win_count / total_trades * 100 if total_trades > 0 else 0

        profits = completed_trades.loc[completed_trades["is_profitable"], "pnl"]
        losses = completed_trades.loc[~completed_trades["is_profitable"], "pnl"]
        avg_profit = profits.mean() if len(profits) > 0 else 0
        avg_loss = abs(losses.mean()) if len(losses) > 0 else 1
        pl_ratio = avg_profit / avg_loss if avg_loss > 0 else float("inf")

        stats_text = f"Win Rate: {win_rate:.1f}%\nP/L Ratio: {pl_ratio:.2f}"
        ax1.text(
            0.98,
            0.05,
            stats_text,
            transform=ax1.transAxes,
            fontsize=10,
            verticalalignment="bottom",
            horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.8, edgecolor="gray"),
        )

    # Legacy: Plot trade signals if provided (scatter method)
    elif trade_signals is not None and not trade_signals.empty:
        buy_signals = trade_signals[trade_signals["signal"] == "BUY"]
        sell_signals = trade_signals[trade_signals["signal"] == "SELL"]

        # Plot buy signals as green triangles pointing up
        ax1.scatter(
            mdates.date2num(buy_signals["date"]),
            buy_signals["price"],
            marker="^",
            color="#26a69a",
            s=100,
            zorder=5,
            label="BUY",
        )

        # Plot sell signals as red triangles pointing down
        ax1.scatter(
            mdates.date2num(sell_signals["date"]),
            sell_signals["price"],
            marker="v",
            color="#ef5350",
            s=100,
            zorder=5,
            label="SELL",
        )

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
