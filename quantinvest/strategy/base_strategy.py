"""Strategy base class for quantitative investing."""

from __future__ import annotations

import backtrader as bt


class BaseStrategy(bt.Strategy):
    """Base strategy that accepts a pre-loaded DataFrame."""

    params = dict(_equity_tracker=None)

    def __init__(self) -> None:
        self.data = self.datas[0]
        self.order: bt.BrokerOrder | None = None

    def start(self) -> None:
        self.p._equity_tracker.clear()
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
            if order.isbuy():
                self.log(f"BUY executed @ {order.executed.price:.2f}")
            else:
                self.log(f"SELL executed @ {order.executed.price:.2f}")
            self.order = None

    def notify_trade(self, trade: bt.Trade) -> None:
        if trade.isclosed:
            self.log(f"PnL gross {trade.pnl:.2f}, net {trade.pnlcomm:.2f}")
