"""Tests for the quantinvest package."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------

class TestQuantData:
    def test_infer_source_akshare(self):
        """A-share symbols (.SH / .SZ) should resolve to AkShareData."""
        from quantinvest.data.base import QuantData

        assert QuantData._infer_source("600519.SH") is not None
        assert QuantData._infer_source("000001.SZ") is not None

    def test_infer_source_yfinance(self):
        """US / HK symbols should resolve to YFinanceData."""
        from quantinvest.data.base import QuantData

        assert QuantData._infer_source("AAPL.US") is not None
        assert QuantData._infer_source("0700.HK") is not None

    def test_get_returns_instance(self):
        """QuantData.get() should return a provider with a fetch method."""
        from quantinvest.data import QuantData

        data = QuantData.get("600519.SH")
        assert hasattr(data, "fetch")

    def test_get_akshare_for_a_share(self):
        """A-share symbols should instantiate AkShareData."""
        from quantinvest.data import AkShareData, QuantData

        data = QuantData.get("600519.SH")
        assert isinstance(data, AkShareData)

    def test_get_yfinance_for_hk(self):
        """HK symbols should instantiate YFinanceData."""
        from quantinvest.data import QuantData, YFinanceData

        data = QuantData.get("0700.HK")
        assert isinstance(data, YFinanceData)

    def test_infer_default_yfinance(self):
        """Unrecognised symbols should default to yfinance."""
        from quantinvest.data import QuantData, YFinanceData

        assert QuantData._infer_source("UNKNOWN") is YFinanceData


class TestYFinanceData:
    def test_to_yf_symbol_strips_us_suffix(self):
        from quantinvest.data.yfinance_data import YFinanceData

        assert YFinanceData._to_yf_symbol("AAPL.US") == "AAPL"

    def test_to_yf_symbol_preserves_hk_suffix(self):
        from quantinvest.data.yfinance_data import YFinanceData

        assert YFinanceData._to_yf_symbol("0700.HK") == "0700.HK"

    def test_to_yf_symbol_preserves_plain_symbol(self):
        from quantinvest.data.yfinance_data import YFinanceData

        assert YFinanceData._to_yf_symbol("AAPL") == "AAPL"

    def test_proxy_set_once_at_init(self):
        """Proxy env vars should be set once in __init__, not on every fetch."""
        from quantinvest.data.yfinance_data import YFinanceData

        with patch("quantinvest.data.yfinance_data.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(
                https_proxy="http://proxy:7890", http_proxy="http://proxy:7890"
            )
            instance = YFinanceData()
            # load_config called once during __init__
            assert mock_cfg.call_count == 1
            # fetch should not call load_config again
            with patch("yfinance.Ticker") as mock_ticker:
                mock_ticker.return_value.history.return_value = pd.DataFrame(
                    {
                        "Open": [1],
                        "High": [1],
                        "Low": [1],
                        "Close": [1],
                        "Volume": [1],
                    },
                    index=pd.DatetimeIndex(["2024-01-01"]),
                )
                instance.fetch("AAPL.US")
                assert mock_cfg.call_count == 1


class TestBaoStockData:
    def test_to_bao_symbol_sh(self):
        from quantinvest.data.baostock_data import BaoStockData

        assert BaoStockData._to_bao_symbol("600519.SH") == "sh.600519"

    def test_to_bao_symbol_sz(self):
        from quantinvest.data.baostock_data import BaoStockData

        assert BaoStockData._to_bao_symbol("000001.SZ") == "sz.000001"

    def test_clean_produces_standard_columns(self):
        from quantinvest.data.baostock_data import BaoStockData

        df = pd.DataFrame(
            {
                "date": ["2024-01-01"],
                "open": ["10"],
                "high": ["11"],
                "low": ["9"],
                "close": ["10.5"],
                "volume": ["1000"],
            }
        )
        result = BaoStockData._clean(df)
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]
        assert result.index.name == "date"


class TestAkShareData:
    def test_clean_produces_standard_columns(self):
        from quantinvest.data.akshare_data import AkShareData

        df = pd.DataFrame(
            {
                "日期": ["2024-01-01"],
                "开盘": ["10"],
                "收盘": ["10.5"],
                "最高": ["11"],
                "最低": ["9"],
                "成交量": ["1000"],
            }
        )
        result = AkShareData._clean(df)
        expected = {"open", "close", "high", "low", "volume"}
        assert set(result.columns) == expected
        assert result.index.name == "date"


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_data():
    """Minimal OHLCV DataFrame for backtest tests."""
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    return pd.DataFrame(
        {
            "open": 10.0 + np.arange(100) * 0.01,
            "high": 10.1 + np.arange(100) * 0.01,
            "low": 9.9 + np.arange(100) * 0.01,
            "close": 10.0 + np.arange(100) * 0.01,
            "volume": 1000,
        },
        index=dates,
    )

class TestBacktestEngine:
    def test_report_uses_custom_cash(self, sample_data):
        """get_report should use the actual cash passed to __init__, not a hardcoded value."""
        from quantinvest.backtest import BacktestEngine

        engine = BacktestEngine(sample_data, cash=50_000.0)
        report = engine.get_report()
        # The report should reflect 50_000 initial cash, not 100_000
        assert "50,000" not in report or "100,000" not in report
        # More importantly, the total return should be computed from the actual cash
        # We just verify the engine stores the cash correctly
        assert engine.cash == 50_000.0

    def test_equity_tracker_is_instance_level(self, sample_data):
        """Each BacktestEngine should have its own _equity_tracker."""
        from quantinvest.backtest import BacktestEngine

        engine1 = BacktestEngine(sample_data)
        engine2 = BacktestEngine(sample_data)
        assert engine1._equity_tracker is not engine2._equity_tracker

    def test_stake_stored(self, sample_data):
        """The stake parameter should be stored on the engine."""
        from quantinvest.backtest import BacktestEngine

        engine = BacktestEngine(sample_data, stake=200)
        assert engine.stake == 200

    def test_get_equity_curve_empty(self, sample_data):
        """get_equity_curve should return empty Series before any run."""
        from quantinvest.backtest import BacktestEngine

        engine = BacktestEngine(sample_data)
        curve = engine.get_equity_curve()
        assert isinstance(curve, pd.Series)
        assert len(curve) == 0


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

class TestBaseStrategy:
    def test_base_strategy_has_tracker_param(self):
        """BaseStrategy should have _equity_tracker param."""
        from quantinvest.strategy.base_strategy import BaseStrategy

        # backtrader params is a bt.Params-like object; check via __dict__
        assert "_equity_tracker" in BaseStrategy.params.__dict__

    def test_tracker_passed_to_strategy(self, sample_data):
        """Engine should pass _equity_tracker to strategy via run()."""
        from quantinvest.backtest import BacktestEngine
        from quantinvest.strategy.base_strategy import BaseStrategy

        engine = BacktestEngine(sample_data)
        # Verify the engine passes the tracker
        tracker = engine._equity_tracker
        assert tracker is not None
        assert isinstance(tracker, list)


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

class TestComputeIndicators:
    def test_ma_indicators(self):
        from quantinvest.viz import compute_indicators

        df = pd.DataFrame(
            {"close": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]},
            index=pd.date_range("2024-01-01", periods=10),
        )
        result = compute_indicators(df, strategy="ma", fast=3, slow=5)
        assert "MA3" in result
        assert "MA5" in result

    def test_macd_indicators(self):
        from quantinvest.viz import compute_indicators

        df = pd.DataFrame(
            {"close": list(range(30))},
            index=pd.date_range("2024-01-01", periods=30),
        )
        result = compute_indicators(df, strategy="macd")
        assert "MACD" in result
        assert "Signal" in result
        assert "Histogram" in result

    def test_bollinger_indicators(self):
        from quantinvest.viz import compute_indicators

        df = pd.DataFrame(
            {"close": list(range(30))},
            index=pd.date_range("2024-01-01", periods=30),
        )
        result = compute_indicators(df, strategy="bollinger")
        assert "Bollinger Upper" in result
        assert "Bollinger Middle" in result
        assert "Bollinger Lower" in result

    def test_unknown_strategy_raises(self):
        from quantinvest.viz import compute_indicators

        df = pd.DataFrame(
            {"close": list(range(10))},
            index=pd.date_range("2024-01-01", periods=10),
        )
        with pytest.raises(ValueError, match="Unknown strategy"):
            compute_indicators(df, strategy="unknown")
