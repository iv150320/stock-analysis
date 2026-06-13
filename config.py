"""Application configuration and constants.

Centralized configuration following the 12-factor app pattern.
All magic numbers, hardcoded dicts, and tunable thresholds live here.
"""

from __future__ import annotations

import os
from typing import Final


# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------

_DEFAULT_SECRET_KEY: Final[str] = "cs50-final-project-dev-only-change-in-prod"

SECRET_KEY: Final[str] = os.environ.get("STOCKSCOPE_SECRET_KEY", _DEFAULT_SECRET_KEY)

# True when the app is falling back to the built-in dev key (i.e. no
# STOCKSCOPE_SECRET_KEY was provided).  app.py warns about this in production.
USING_DEFAULT_SECRET: Final[bool] = SECRET_KEY == _DEFAULT_SECRET_KEY

DEBUG: Final[bool] = os.environ.get("FLASK_DEBUG", "0") == "1"

HOST: Final[str] = os.environ.get("FLASK_HOST", "0.0.0.0")
PORT: Final[int] = int(os.environ.get("FLASK_PORT", "5000"))


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

CACHE_DURATION: Final[int] = int(os.environ.get("STOCKSCOPE_CACHE_TTL", "300"))
CACHE_MAX_ENTRIES: Final[int] = int(os.environ.get("STOCKSCOPE_CACHE_MAX", "128"))


# ---------------------------------------------------------------------------
# Data source
# ---------------------------------------------------------------------------

# Periods accepted by yfinance.download, in display order.  This tuple is the
# single source of truth: ``ALLOWED_PERIODS`` (membership checks), the CLI
# ``--period`` help text, and the README all derive from it.
PERIODS: Final[tuple[str, ...]] = (
    "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max",
)
ALLOWED_PERIODS: Final[frozenset[str]] = frozenset(PERIODS)
DEFAULT_PERIOD: Final[str] = "1y"

# yfinance download / HTTP timeout (seconds)
YFINANCE_TIMEOUT: Final[int] = int(os.environ.get("STOCKSCOPE_YF_TIMEOUT", "30"))


# ---------------------------------------------------------------------------
# Markets — S&P 500 sectors & constituents (160 tickers across 8 sectors)
# ---------------------------------------------------------------------------

SECTORS: Final[dict[str, list[str]]] = {
    "Technology": [
        "AAPL", "MSFT", "NVDA", "GOOGL", "META", "CRM", "ADBE", "ORCL", "QCOM", "AMD",
        "INTC", "TXN", "CSCO", "IBM", "NOW", "AMAT", "MU", "ADI", "ADP", "FIS",
    ],
    "Finance": [
        "JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "BLK", "SCHW", "USB",
        "PNC", "TFC", "BK", "COF", "SPGI", "MCO", "MET", "AIG", "PRU", "AFL",
    ],
    "Healthcare": [
        "UNH", "PFE", "ABBV", "MRK", "ABT", "LLY", "TMO", "JNJ", "BMY", "AMGN",
        "CVS", "MDT", "ISRG", "SYK", "GILD", "BSX", "REGN", "VRTX", "CI", "BDX",
    ],
    "Consumer Cyclical": [
        "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "BKNG", "TGT", "TJX",
        "ROST", "GM", "F", "EBAY", "MAR", "HLT", "DRI", "YUM", "CMG", "AZO",
    ],
    "Energy": [
        "XOM", "CVX", "COP", "SLB", "EOG", "OXY", "MPC", "PSX", "VLO", "KMI",
        "HAL", "BKR", "DVN", "FANG", "CTRA", "TRGP", "EQT", "WMB", "OKE", "SU",
    ],
    "Communication": [
        "GOOG", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "CHTR", "TMUS", "EA",
        "TTWO", "WBD", "OMC", "NWSA", "FOXA", "LYV", "MTCH", "SNAP", "SPOT", "ROKU",
    ],
    "Industrials": [
        "CAT", "GE", "BA", "HON", "UNP", "UPS", "RTX", "LMT", "MMM", "GD",
        "NOC", "CSX", "FDX", "DE", "CARR", "ETN", "EMR", "ITW", "PAYX", "PH",
    ],
    "Utilities": [
        "NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "ED", "PEG",
        "WEC", "AWK", "ES", "DTE", "AEE", "CNP", "EIX", "FE", "CMS", "ATO",
    ],
}


def get_default_tickers() -> list[str]:
    """Flat list of tickers across all sectors (order preserved)."""
    return [t for sector in SECTORS.values() for t in sector]


DEFAULT_TICKERS: Final[list[str]] = get_default_tickers()


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

TRADING_DAYS_PER_YEAR: Final[int] = 252


def is_valid_period(period: str) -> bool:
    """Return True iff `period` is part of the yfinance whitelist."""
    return period in ALLOWED_PERIODS
