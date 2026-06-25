"""Strategy base class for quantitative investing."""

from __future__ import annotations

import backtrader as bt


class BaseStrategy(bt.Strategy):
    """Base strategy that accepts a pre-loaded DataFrame."""

    params = dict(_equity_tracker=None, _trade_signals=None, _completed_trades=None)

    def __init__(self) -> None:
        self.data = self.datas[0]
        self.order: bt.BrokerOrder | None = None
        self._last_buy_date: object = None
        self._last_buy_price: float = 0.0
        self._last_sell_price: float = 0.0

    def start(self) -> None:
        self.p._equity_tracker.clear()
        self.p._trade_signals.clear()
        self.p._completed_trades.clear()
        self.log("Strategy started")

    def log(self, txt: str) -> None:
        dt_str = self.datas[0].datetime.date(0).strftime("%Y-%m-%d")
        print(f"[{dt_str}] {txt}")

    def next(self) -> None:
        self.p._equity_tracker.append(
            (self.data.datetime.date(0), self.broker.getvalue())
        )
        if self.order:
            return
        # Subclass must implement
        pass

    def notify_order(self, order: bt.BrokerOrder) -> None:
        if order.status == order.Completed:
            dt = self.data.datetime.date(0)
            price = order.executed.price
            if order.isbuy():
                self._last_buy_date = dt
                self._last_buy_price = price
                self.log(f"BUY executed @ {price:.2f}")
                self.p._trade_signals.append((dt, "BUY", price))
            else:
                self._last_sell_price = price
                self.log(f"SELL executed @ {price:.2f}")
                self.p._trade_signals.append((dt, "SELL", price))
            self.order = None

    def notify_trade(self, trade: bt.Trade) -> None:
        if trade.isclosed:
            self.log(f"PnL gross {trade.pnl:.2f}, net {trade.pnlcomm:.2f}")
            # Record completed trade: (buy_date, sell_date, buy_price, sell_price, pnl, is_profitable)
            self.p._completed_trades.append(
                (self._last_buy_date, self.data.datetime.date(0), self._last_buy_price, self._last_sell_price, trade.pnl, trade.pnl > 0)
            )
