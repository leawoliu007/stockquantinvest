"""QuantInvest configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Application-wide configuration."""

    # Proxy settings (for yfinance / external APIs)
    http_proxy: str = field(default_factory=lambda: os.environ.get("HTTP_PROXY", ""))
    https_proxy: str = field(default_factory=lambda: os.environ.get("HTTPS_PROXY", ""))


def load_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        http_proxy=os.environ.get("HTTP_PROXY", ""),
        https_proxy=os.environ.get("HTTPS_PROXY", ""),
    )
