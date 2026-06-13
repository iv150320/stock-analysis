"""Unit tests for :mod:`config`."""

from config import (
    ALLOWED_PERIODS,
    DEFAULT_PERIOD,
    DEFAULT_TICKERS,
    PERIODS,
    SECTORS,
    is_valid_period,
)


def test_sectors_eight_categories():
    assert len(SECTORS) == 8


def test_default_tickers_unique():
    """The 160-element ticker list may contain intentional cross-sector
    duplicates (e.g. META appears in both Technology and Communication); we
    just verify the per-sector block sizes add up to 160.
    """
    assert len(DEFAULT_TICKERS) == 160
    flat = sum((v for v in SECTORS.values()), [])
    assert len(flat) == 160


def test_membership_of_meta_in_dual_sector():
    """META is intentionally listed in both Technology and Communication,
    reflecting real-world S&P 500 GICS classifications.
    """
    assert "META" in SECTORS["Technology"]
    assert "META" in SECTORS["Communication"]


def test_each_sector_has_20_constituents():
    for name, tickers in SECTORS.items():
        assert len(tickers) == 20, f"{name} has {len(tickers)} tickers"


def test_allowed_periods_whitelist():
    assert DEFAULT_PERIOD in ALLOWED_PERIODS
    assert is_valid_period("1y")
    assert is_valid_period("5d")
    assert not is_valid_period("999y")
    assert not is_valid_period("")
    assert not is_valid_period("hack")
    # `1d` is intentionally not whitelisted (a single day yields no return /
    # volatility); `ytd` is.
    assert not is_valid_period("1d")
    assert is_valid_period("ytd")


def test_periods_is_single_source_of_truth():
    """PERIODS (display order) and ALLOWED_PERIODS (membership) must agree."""
    assert set(PERIODS) == set(ALLOWED_PERIODS)
    assert len(PERIODS) == len(set(PERIODS))  # no duplicates
    assert all(is_valid_period(p) for p in PERIODS)
