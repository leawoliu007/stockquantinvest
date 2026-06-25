"""QuantInvest configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# Project root for default paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    """Application-wide configuration."""

    # Proxy settings (for yfinance / external APIs)
    http_proxy: str = field(default_factory=lambda: os.environ.get("HTTP_PROXY", ""))
    https_proxy: str = field(default_factory=lambda: os.environ.get("HTTPS_PROXY", ""))

    # Database & watchlist
    db_path: str = field(default_factory=lambda: str(_PROJECT_ROOT / "data.db"))
    watchlist_file: str = field(default_factory=lambda: str(_PROJECT_ROOT / "watchlist.json"))


def load_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        http_proxy=os.environ.get("HTTP_PROXY", ""),
        https_proxy=os.environ.get("HTTPS_PROXY", ""),
        db_path=os.environ.get("QUANTINVEST_DB", str(_PROJECT_ROOT / "data.db")),
        watchlist_file=os.environ.get("QUANTINVEST_WATCHLIST", str(_PROJECT_ROOT / "watchlist.json")),
    )
