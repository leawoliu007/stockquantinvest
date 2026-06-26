from __future__ import annotations

import datetime as dt

import akshare as ak
import pandas as pd


# Map user-facing freq names to AKShare period values
_FREQ_MAP: dict[str, str] = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
}

# Minute-level frequencies
_MIN_FREQ_MAP: dict[str, str] = {
    "30min": "30",
    "15min": "15",
    "60min": "60",
    "5min": "5",
    "1min": "1",
}


class AkShareData:
    """Fetch A-stock and ETF data from AKShare (real-time + historical)."""

    @staticmethod
    def _is_etf(symbol: str) -> bool:
        """Check if symbol is an ETF."""
        code = symbol.replace(".SH", "").replace(".SZ", "").replace(".ETF", "")
        # ETF codes: 5xxx/1xxx (Shanghai), 15xx/16xx (Shenzhen)
        return code.startswith(("5", "15", "16"))

    def fetch(
        self,
        symbol: str,
        start: str | dt.date = "2020-01-01",
        end: str | dt.date = dt.date.today().strftime("%Y-%m-%d"),
        freq: str = "daily",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        is_etf = self._is_etf(symbol)
        code = symbol.replace(".SH", "").replace(".SZ", "").replace(".ETF", "")

        # Determine if this is a minute-level frequency
        is_minute = freq in _MIN_FREQ_MAP

        # If caching enabled for minute data, try incremental update from DB
        if use_cache and is_minute:
            period = _MIN_FREQ_MAP[freq]
            from .database import QuantDB

            db = QuantDB()
            try:
                latest = db.get_latest_date(code, freq)
                if latest:
                    # Fetch only new data
                    cached_df = db.fetch_cached(code, freq=freq, start=start, end=latest)
                    new_start = (latest + dt.timedelta(days=1)).strftime("%Y-%m-%d")
                    new_df = self._raw_fetch_min(code, period, new_start, str(end), is_etf=is_etf)
                    if not new_df.empty:
                        db.save_kline(new_df, code, freq)
                    result = pd.concat([cached_df, new_df])
                    result = result[~result.index.duplicated(keep="last")]
                    result = result.sort_index()
                    return result
                else:
                    # No cache yet, fetch all and store
                    result = self._raw_fetch_min(code, period, str(start), str(end), is_etf=is_etf)
                    if not result.empty:
                        db.save_kline(result, code, freq)
                    return result
            finally:
                db.close()

        # Daily/weekly/monthly data
        period = _FREQ_MAP.get(freq, "daily")
        return self._raw_fetch(code, period, str(start), str(end), is_etf=is_etf)

    def _raw_fetch(
        self,
        code: str,
        period: str,
        start: str,
        end: str,
        is_etf: bool = False,
    ) -> pd.DataFrame:
        if is_etf:
            df = ak.fund_etf_hist_em(
                symbol=code,
                period=period,
                start_date=str(start).replace("-", ""),
                end_date=str(end).replace("-", ""),
                adjust="qfq",
            )
            return self._clean_etf(df)
        else:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=str(start).replace("-", ""),
                end_date=str(end).replace("-", ""),
                adjust="qfq",
            )
            return self._clean(df)

    def _raw_fetch_min(
        self,
        code: str,
        period: str,
        start: str,
        end: str,
        is_etf: bool = False,
    ) -> pd.DataFrame:
        """Fetch minute-level data.

        For stocks: uses Sina (stock_zh_a_minute) — recent data only (~1970 bars).
        For ETFs: uses Eastmoney (fund_etf_hist_min_em) — full date range support.
        """
        if is_etf:
            df = ak.fund_etf_hist_min_em(
                symbol=code,
                start_date=f"{start} 09:30:00",
                end_date=f"{end} 15:00:00",
                period=period,
                adjust="qfq",
            )
            return self._clean_min_em(df)

        # Stock — Sina source
        if code.startswith(("6", "9")):
            sina_symbol = f"sh{code}"
        else:
            sina_symbol = f"sz{code}"

        df = ak.stock_zh_a_minute(symbol=sina_symbol, period=period, adjust="qfq")
        result = self._clean_min_sina(df)

        # Filter by date range if provided
        if start:
            result = result[result.index >= pd.Timestamp(start)]
        if end:
            result = result[result.index <= pd.Timestamp(end)]
        return result

    @staticmethod
    def _clean_min_sina(df: pd.DataFrame) -> pd.DataFrame:
        """Clean minute-level data from stock_zh_a_minute (Sina source)."""
        cols = {
            "day": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }
        available = {k: v for k, v in cols.items() if k in df.columns}
        df = df.rename(columns=available).filter(list(cols.values()))
        df["date"] = pd.to_datetime(df["date"])
        for col in ("open", "close", "high", "low", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.set_index("date").sort_index()

    @staticmethod
    def _clean_min_em(df: pd.DataFrame) -> pd.DataFrame:
        """Clean minute-level data from fund_etf_hist_min_em (Eastmoney source)."""
        cols = {
            "时间": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
        }
        available = {k: v for k, v in cols.items() if k in df.columns}
        df = df.rename(columns=available).filter(list(cols.values()))
        df["date"] = pd.to_datetime(df["date"])
        for col in ("open", "close", "high", "low", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.set_index("date").sort_index()

    def fetch_realtime(self, symbol: str) -> pd.DataFrame:
        code = symbol.replace(".SH", "").replace(".SZ", "").replace(".ETF", "")
        if self._is_etf(symbol):
            df = ak.fund_etf_spot_em()
            mask = df["代码"] == code
            return df[mask].reset_index(drop=True)
        else:
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

    @staticmethod
    def _clean_etf(df: pd.DataFrame) -> pd.DataFrame:
        """Clean ETF data from fund_etf_hist_em."""
        cols = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
        }
        available = {k: v for k, v in cols.items() if k in df.columns}
        df = df.rename(columns=available).filter(list(cols.values()))
        df["date"] = pd.to_datetime(df["date"])
        for col in ("open", "close", "high", "low", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.set_index("date").sort_index()
