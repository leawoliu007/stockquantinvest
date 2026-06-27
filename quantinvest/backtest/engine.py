"""Backtest engine wrapping backtrader Cerebro."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Type

import backtrader as bt
import pandas as pd


class BacktestEngine:
    """Run a strategy on historical data and return results."""

    def __init__(
        self,
        data: pd.DataFrame,
        cash: float = 100_000.0,
        commission: float = 0.001,
        stake: int = 100,
    ) -> None:
        self.dataframe = data
        self.cash = cash
        self.stake = stake
        self._equity_tracker: list[tuple] = []
        self._trade_signals: list[tuple] = []
        self._completed_trades: list[tuple] = []

        self.cerebro = bt.Cerebro()
        self.cerebro.broker.setcash(cash)
        self.cerebro.broker.setcommission(commission=commission)
        self.cerebro.addsizer(bt.sizers.PercentSizer, percents=95)

        # Feed data into cerebro
        data_feed = bt.feeds.PandasData(
            dataname=data,
            datetime=None,
            openinterest=-1,
            volume="volume",
            open="open",
            high="high",
            low="low",
            close="close",
        )
        self.cerebro.adddata(data_feed)

    def run(self, strategy: Type, **kwargs: Any) -> bt.analyzers.Snapshot:
        """Run the strategy and return analyzers."""
        self.cerebro.addstrategy(
            strategy,
            _equity_tracker=self._equity_tracker,
            _trade_signals=self._trade_signals,
            _completed_trades=self._completed_trades,
            **kwargs,
        )
        results = self.cerebro.run()

        # Force close any remaining position at last bar's close price
        pos = self.cerebro.broker.getposition(self.cerebro.datas[0])
        if pos.size > 0:
            last_close = self.dataframe["close"].iloc[-1]
            self.cerebro.broker.cash += pos.size * last_close
            pos.size = 0
            pos.price = 0.0

        return results[0]

    def get_equity_curve(self) -> pd.Series:
        """Return the equity curve as a pd.Series indexed by date."""
        if not self._equity_tracker:
            return pd.Series(dtype=float)
        dates, values = zip(*self._equity_tracker)
        return pd.Series(values, index=pd.Index(dates))

    def get_trade_signals(self) -> pd.DataFrame:
        """Return trade signals as a DataFrame with columns: date, signal, price."""
        if not self._trade_signals:
            return pd.DataFrame(columns=["date", "signal", "price"])
        return pd.DataFrame(self._trade_signals, columns=["date", "signal", "price"])

    def get_completed_trades(self) -> pd.DataFrame:
        """Return completed trades as a DataFrame.

        Columns: buy_date, sell_date, buy_price, sell_price, pnl, is_profitable
        """
        if not self._completed_trades:
            return pd.DataFrame(columns=["buy_date", "sell_date", "buy_price", "sell_price", "pnl", "is_profitable"])
        return pd.DataFrame(
            self._completed_trades, columns=["buy_date", "sell_date", "buy_price", "sell_price", "pnl", "is_profitable"]
        )

    def get_report(self) -> str:
        """Return a text summary of portfolio performance."""
        portvalue = self.cerebro.broker.getvalue()
        total_return = (portvalue - self.cash) / self.cash * 100
        return f"Final Value: {portvalue:,.2f}\nTotal Return: {total_return:.2f}%"

    def plot(self, filename: str | Path | None = None, **kwargs: Any) -> None:
        """Plot the backtest results."""
        kwargs.setdefault("style", "candlestick")
        kwargs.setdefault("volume", True)
        plot_kwargs = {k: v for k, v in kwargs.items() if k not in ("filename",)}

        if filename:
            figs = self.cerebro.plot(**plot_kwargs)
            # figs is a list of figure groups (one per strategy); save the first
            for fig in figs[0]:
                fig.savefig(filename, dpi=150)
                fig.clf()
            print(f"Chart saved to {filename}")
        else:
            self.cerebro.plot(**plot_kwargs)
