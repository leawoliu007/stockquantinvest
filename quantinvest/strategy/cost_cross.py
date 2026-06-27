"""Cost cross strategy: MA crosses COST(N).

Buy signal:  MA crosses above COST(cost_buy_pct)
Sell signal: MA crosses below COST(cost_sell_pct)

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
    """MA crosses COST(N) strategy.

    Buy:  MA crosses above COST(cost_buy_pct)
    Sell: MA crosses below COST(cost_sell_pct)

    Params:
        ma_period (int): Moving average period (default 5)
        cost_buy_pct (float): COST percentile for buy signal (default 80)
        cost_sell_pct (float): COST percentile for sell signal (default 80)
        decay_half_life (int): Chip decay half-life in days (default 60)
        num_bins (int): Price bin count (default 200)
        spread_pct (float): Gaussian spread ratio (default 0.015)
        warmup (int): Minimum bars before trading (default 30)
    """

    params = dict(
        ma_period=5,
        cost_buy_pct=80,
        cost_sell_pct=80,
        decay_half_life=60,
        num_bins=200,
        spread_pct=0.015,
        warmup=30,
    )

    def __init__(self) -> None:
        super().__init__()
        self.ma = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        self._chips: list[float] = []
        self._prev_cost_buy: float | None = None
        self._prev_cost_sell: float | None = None
        self._min_p: float | None = None
        self._max_p: float | None = None
        self._bin_width: float | None = None
        self._decay: float = 1.0

    def start(self) -> None:
        super().start()
        self._chips = [0.0] * self.p.num_bins

    def _ensure_bin_setup(self) -> bool:
        if self._min_p is not None:
            return True
        try:
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

        if len(self.data.close) < self.p.warmup or len(self.ma) < 2:
            return

        if not self._ensure_bin_setup():
            return

        close = self.data.close[0]
        vol = self.data.volume[0] if hasattr(self.data, "volume") and self.data.volume[0] > 0 else 0

        # Save previous COST values before updating chips
        cost_buy_prev = self._prev_cost_buy
        cost_sell_prev = self._prev_cost_sell

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

        # Compute current COST values
        cost_buy_now = self._compute_cost(self.p.cost_buy_pct)
        cost_sell_now = self._compute_cost(self.p.cost_sell_pct)

        # Update previous for next bar
        self._prev_cost_buy = cost_buy_now
        self._prev_cost_sell = cost_sell_now

        # Safely get MA values
        try:
            ma_now = float(self.ma[0])
            ma_prev = float(self.ma[-1])
        except (ValueError, TypeError):
            return

        # Skip if COST values not ready
        if any(v is None for v in [cost_buy_now, cost_buy_prev, cost_sell_now, cost_sell_prev]):
            return

        # --- Buy: MA crosses above COST(cost_buy_pct) ---
        buy_signal = (ma_prev < cost_buy_prev) and (ma_now > cost_buy_now)

        # --- Sell: MA crosses below COST(cost_sell_pct) ---
        sell_signal = (ma_prev > cost_sell_prev) and (ma_now < cost_sell_now)

        if not self.position:
            if buy_signal:
                self.buy()
        else:
            if sell_signal:
                self.close()
