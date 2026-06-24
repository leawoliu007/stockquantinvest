from __future__ import annotations

import datetime as dt
from typing import ClassVar

import akshare as ak
import pandas as pd


class AkShareData:
    """Fetch A-stock data from AKShare (real-time + historical)."""

    def fetch(
        self,
        symbol: str,
        start: str | dt.date = "2020-01-01",
        end: str | dt.date = dt.date.today().strftime("%Y-%m-%d"),
        freq: str = "daily",
    ) -> pd.DataFrame:
        if symbol.startswith(("0", "3")):
            market = "sz"
        elif symbol.startswith(("6", "9")):
            market = "sh"
        else:
            market = "sh"

        code = symbol.replace(".SH", "").replace(".SZ", "")
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=str(start).replace("-", ""),
            end_date=str(end).replace("-", ""),
            adjust="qfq",
        )
        return self._clean(df)

    def fetch_realtime(self, symbol: str) -> pd.DataFrame:
        code = symbol.replace(".SH", "").replace(".SZ", "")
        df = ak.stock_zh_a_spot_em()
        mask = df["代码"] == code
        return df[mask].reset_index(drop=True)

    @staticmethod
    def _clean(df: pd.DataFrame) -> pd.DataFrame:
        cols = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
        }
        df = df.rename(columns=cols).filter(list(cols.values()))
        df["date"] = pd.to_datetime(df["date"])
        for col in ("open", "close", "high", "low", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.set_index("date").sort_index()
