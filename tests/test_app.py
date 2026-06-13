"""Unit tests for :mod:`app` helpers.

These cover the pure helpers (no network / yfinance), focusing on the
``None``-handling and validation logic that guards the Flask routes.
"""

import math

import pytest

from app import TTLCache, mean_ignore_none, normalise_period, safe_round
from config import DEFAULT_PERIOD


# ---------------------------------------------------------------------------
# safe_round
# ---------------------------------------------------------------------------

def test_safe_round_numeric():
    assert safe_round(1.23456, 2) == 1.23
    assert safe_round(10, 2) == 10.0


def test_safe_round_handles_none_and_nan():
    assert safe_round(None) is None
    assert safe_round(float("nan")) is None
    assert safe_round("not-a-number") is None


# ---------------------------------------------------------------------------
# mean_ignore_none
# ---------------------------------------------------------------------------

def test_mean_ignore_none_skips_none():
    assert mean_ignore_none([1.0, None, 3.0]) == 2.0


def test_mean_ignore_none_all_none_returns_zero():
    assert mean_ignore_none([None, None]) == 0
    assert mean_ignore_none([]) == 0


def test_mean_ignore_none_rounds():
    assert mean_ignore_none([1.0, 2.0], ndigits=2) == 1.5
    assert mean_ignore_none([1.0, 1.0, 1.0, 2.0], ndigits=3) == 1.25


# ---------------------------------------------------------------------------
# normalise_period
# ---------------------------------------------------------------------------

def test_normalise_period_valid_passthrough():
    assert normalise_period("3mo") == "3mo"
    assert normalise_period("ytd") == "ytd"


def test_normalise_period_falls_back_on_invalid():
    assert normalise_period(None) == DEFAULT_PERIOD
    assert normalise_period("") == DEFAULT_PERIOD
    assert normalise_period("1d") == DEFAULT_PERIOD
    assert normalise_period("hack") == DEFAULT_PERIOD


# ---------------------------------------------------------------------------
# TTLCache
# ---------------------------------------------------------------------------

def test_ttl_cache_get_set():
    c = TTLCache(max_size=4, ttl=300)
    assert c.get("missing") is None
    c.set("a", 1)
    assert c.get("a") == 1


def test_ttl_cache_expiry(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.time.time", lambda: now[0])
    c = TTLCache(max_size=4, ttl=10)
    c.set("a", 1)
    assert c.get("a") == 1
    now[0] += 11  # advance past ttl
    assert c.get("a") is None


def test_ttl_cache_lru_eviction():
    c = TTLCache(max_size=2, ttl=300)
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")          # touch 'a' so 'b' is now least-recently-used
    c.set("c", 3)       # evicts 'b'
    assert c.get("a") == 1
    assert c.get("c") == 3
    assert c.get("b") is None


def test_ttl_cache_rejects_bad_size():
    with pytest.raises(ValueError):
        TTLCache(max_size=0, ttl=10)
