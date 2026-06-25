"""Tests for SQLite database layer."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date

import pandas as pd
import pytest

from quantinvest.data.database import QuantDB


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    instance = QuantDB(db_path)
    yield instance
    instance.close()


@pytest.fixture
def watchlist_file(tmp_path):
    wl_path = tmp_path / "watchlist.json"
    data = [
        {"symbol": "600519.SH", "name": "贵州茅台", "market": "CN"},
        {"symbol": "000001.SZ", "name": "平安银行", "market": "CN"},
    ]
    with open(wl_path, "w") as f:
        json.dump(data, f)
    return wl_path


class TestWatchlist:
    def test_save_watchlist_from_file(self, db, watchlist_file):
        db.save_watchlist_from_file(watchlist_file)
        items = db.get_watchlist()
        assert len(items) == 2
        symbols = [i["symbol"] for i in items]
        assert "600519.SH" in symbols
        assert "000001.SZ" in symbols

    def test_save_from_nonexistent_file_is_noop(self, db):
        db.save_watchlist_from_file("/tmp/does_not_exist.json")
        assert db.get_watchlist() == []

    def test_add_and_remove(self, db):
        db.add_watchlist("0700.HK", "腾讯", "HK")
        items = db.get_watchlist()
        assert len(items) == 1
        assert items[0]["symbol"] == "0700.HK"

        db.remove_watchlist("0700.HK")
        assert db.get_watchlist() == []

    def test_add_duplicate_is_ignored(self, db):
        db.add_watchlist("600519.SH", "茅台", "CN")
        db.add_watchlist("600519.SH", "贵州茅台", "CN")
        assert len(db.get_watchlist()) == 1


class TestKline:
    @staticmethod
    def _make_df() -> pd.DataFrame:
        data = {
            "open": [10, 11, 12],
            "high": [11, 12, 13],
            "low": [9, 10, 11],
            "close": [10.5, 11.5, 12.5],
            "volume": [1000, 2000, 3000],
        }
        return pd.DataFrame(data, index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))

    def test_save_and_fetch_cached(self, db):
        df = self._make_df()
        db.save_kline(df, "600519.SH", "daily")
        result = db.fetch_cached("600519.SH", "daily")
        assert len(result) == 3
        assert result["close"].iloc[0] == 10.5

    def test_get_latest_date(self, db):
        df = self._make_df()
        db.save_kline(df, "600519.SH", "daily")
        latest = db.get_latest_date("600519.SH", "daily")
        assert latest == date(2024, 1, 3)

    def test_get_latest_date_empty(self, db):
        assert db.get_latest_date("NOEXIST", "daily") is None

    def test_fetch_cached_returns_empty_when_no_data(self, db):
        result = db.fetch_cached("NOEXIST", "daily")
        assert result.empty

    def test_clear_kline(self, db):
        df = self._make_df()
        db.save_kline(df, "600519.SH", "daily")
        assert len(db.fetch_cached("600519.SH", "daily")) == 3
        db.clear_kline("600519.SH", "daily")
        assert db.fetch_cached("600519.SH", "daily").empty

    def test_different_freq_isolated(self, db):
        df = self._make_df()
        db.save_kline(df, "600519.SH", "daily")
        db.save_kline(df, "600519.SH", "30min")
        assert len(db.fetch_cached("600519.SH", "daily")) == 3
        assert len(db.fetch_cached("600519.SH", "30min")) == 3

    def test_fetch_with_date_range(self, db):
        df = self._make_df()
        db.save_kline(df, "600519.SH", "daily")
        result = db.fetch_cached("600519.SH", "daily", start="2024-01-02", end="2024-01-03")
        assert len(result) == 2
