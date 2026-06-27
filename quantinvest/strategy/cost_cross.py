"""Cost cross strategy: MA5 crosses COST(20) / COST(80).

Buy signal: MA5 crosses above COST(20)
Sell signal: MA5 crosses below COST(20) or COST(80)

COST calculation follows TongDaXin algorithm:
- Price bins with volume-weighted chip distribution
- Daily decay (half-life ~60 days) for chip turnover simulation
- Gaussian spread at daily close price
"""

from __future__ import annotations

import math

import backtrader as bt

from quantinvest.strategy.base_strategy import BaseStrategy


class CostCrossStrategy(BaseStrategy):
    """MA5 crosses COST(20)/COST(80) strategy."""

    params = dict(
        ma_period=5,
        cost_percentiles=(20, 80),
        decay_half_life=60,
        num_bins=200,
        spread_pct=0.015,
        warmup=30,
    )

    def __init__(self) -> None:
        super().__init__()
        self.ma5 = bt.indicators.SMA(self.data.close, period=self.p.ma_period)

        # Chip distribution state
        self._chips = []  # will be initialized in next()
        self._cost20_history = []
        self._cost80_history = []
        self._min_p = None
        self._max_p = None
        self._bin_width = None
        self._decay = 1.0

    def start(self) -> None:
        super().start()
        # Initialize chip distribution state
        self._chips = [0.0] * self.p.num_bins

    def _ensure_bin_setup(self) -> bool:
        """Set up price bins on first call to next(). Returns False if not ready."""
        if self._min_p is not None:
            return True
        try:
            # Use current data range, expand as we see more bars
            closes = [self.data.close[i] for i in range(min(len(self.data.close), 200))]
            if not closes:
                return False
            self._min_p = min(closes) * 0.95
            self._max_p = max(closes) * 1.05
            self._bin_width = (self._max_p - self._min_p) / self.p.num_bins
            self._decay = 0.5 ** (1 / self.p.decay_half_life)
            return True
        except Exception:
            return False

    def _price_to_bin(self, price: float) -> int:
        return min(
            self.p.num_bins - 1,
            max(0, int((price - self._min_p) / self._bin_width)),
        )

    def _compute_cost(self, percentile: float) -> float | None:
        """Find price at which given percentile of chips are below."""
        total = sum(self._chips)
        if total == 0:
            return None
        cum = 0.0
        for b in range(self.p.num_bins):
            cum += self._chips[b]
            if cum / total * 100 >= percentile:
                return self._min_p + (b + 0.5) * self._bin_width
        return None

    def next(self) -> None:
        super().next()

        # Need minimum warmup bars and MA must be ready
        if len(self.data.close) < self.p.warmup or len(self.ma5) < 2:
            return

        # Ensure price bins are initialized
        if not self._ensure_bin_setup():
            return

        close = self.data.close[0]
        vol = self.data.volume[0] if hasattr(self.data, "volume") and self.data.volume[0] > 0 else 0

        # Decay existing chips
        for b in range(self.p.num_bins):
            self._chips[b] *= self._decay

        # Add new chips at today's close (Gaussian spread)
        center_bin = self._price_to_bin(close)
        spread = max(2, int(self.p.spread_pct * (self._max_p - self._min_p) / self._bin_width))
        for offset in range(-spread, spread + 1):
            bin_idx = center_bin + offset
            if 0 <= bin_idx < self.p.num_bins:
                weight = (-(offset ** 2) / (2 * spread * 0.3))
                self._chips[bin_idx] += vol * math.exp(weight)

        # Compute COST(20) and COST(80)
        cost20_now = self._compute_cost(20)
        cost80_now = self._compute_cost(80)

        # Store history for crossover detection
        self._cost20_history.append(cost20_now)
        self._cost80_history.append(cost80_now)

        # Need at least 2 data points to detect crossover
        if len(self._cost20_history) < 2:
            return

        # Safely get MA values (backtrader may return None before warmup)
        try:
            ma5_now = float(self.ma5[0])
            ma5_prev = float(self.ma5[-1])
        except (ValueError, TypeError):
            return

        cost20_now = self._cost20_history[-1]
        cost20_prev = self._cost20_history[-2]
        cost80_now = self._cost80_history[-1]

        # Skip if any value is None or NaN
        try:
            if any(v is None or math.isnan(v) for v in [ma5_now, ma5_prev, cost20_now, cost20_prev]):
                return
        except TypeError:
            return  # comparison failed due to None/NaN

        # Buy: MA5 crosses above COST(20) — MA5 was below, now above
        buy_signal = (ma5_prev < cost20_prev) and (ma5_now > cost20_now)

        # Sell: MA5 crosses below COST(20) or COST(80)
        sell_signal_cost20 = (ma5_prev > cost20_prev) and (ma5_now < cost20_now)
        sell_signal_cost80 = False
        if cost80_now is not None and ma5_prev > cost80_now:
            sell_signal_cost80 = ma5_now < cost80_now

        if not self.position:
            if buy_signal:
                self.buy()
        else:
            if sell_signal_cost20 or sell_signal_cost80:
                self.close()
