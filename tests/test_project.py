"""Unit tests for :mod:`project`.

The heavy yfinance calls are exercised in integration tests; here we focus
on the deterministic math (``calc_returns``, ``sector_analysis``,
``top_performers``) using tiny synthetic ``Series``/``DataFrame`` inputs that
match the MultiIndex shape produced by yfinance.
"""

import math
import threading

import numpy as np
import pandas as pd
import pytest

from project import calc_returns, sector_analysis, time_limit, top_performers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_prices(closes: dict[str, list[float]]) -> pd.DataFrame:
    """Build a yfinance-shaped DataFrame with MultiIndex (Price, Ticker).

    yfinance.download() with auto_adjust=True returns columns shaped like
    ``(Price level='Close', Ticker)`` — outer level is the metric, inner
    is the symbol.  Tests must mirror that exactly or ``calc_returns`` will
    fail with ``KeyError: 'Close'``.
    """
    n = len(next(iter(closes.values())))
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    pairs = {("Close", ticker): values for ticker, values in closes.items()}
    wide = pd.DataFrame(pairs, index=dates)
    wide.columns = pd.MultiIndex.from_tuples(
        wide.columns, names=["Price", "Ticker"]
    )
    wide.columns = wide.columns.set_levels(
        [wide.columns.levels[0], wide.columns.levels[1]]
    )
    return wide


@pytest.fixture
def two_stock_data():
    """AAPL goes up 50%, MSFT goes up ~25% (linear ramp from 100, doubling)."""
    return _make_prices({
        "AAPL": [100.0, 110.0, 120.0, 130.0, 140.0, 150.0],
        "MSFT": [100.0, 105.0, 110.0, 115.0, 120.0, 125.0],
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_calc_returns_total_return_positive(two_stock_data):
    prices, _, total_return, _ = calc_returns(two_stock_data)
    assert total_return["AAPL"] == pytest.approx(0.5, rel=1e-3)
    assert total_return["MSFT"] == pytest.approx(0.25, rel=1e-3)
    assert total_return["AAPL"] > total_return["MSFT"]


def test_calc_returns_volatility_finite(two_stock_data):
    _, returns, _, vol = calc_returns(two_stock_data)
    assert np.isfinite(vol["AAPL"])
    assert vol["AAPL"] >= 0


def test_calc_returns_empty():
    empty = _make_prices({"ZZZ": []})
    prices, returns, total, vol = calc_returns(empty)
    assert total.empty


def test_top_performers_worst_is_correct_order():
    s = pd.Series([0.5, 0.1, -0.2, -0.05, 0.3], index=["A", "B", "C", "D", "E"])
    best, worst = top_performers(s, n=2)
    assert best.iloc[0] == 0.5
    assert best.iloc[1] == 0.3
    # worst should be the two lowest-return tickers
    assert set(worst.index) == {"C", "D"}
    # and now sorted descending (matches the original CLI plot convention)
    assert worst.iloc[0] >= worst.iloc[-1]


def test_time_limit_runs_off_main_thread():
    """SIGALRM can't be armed outside the main thread; ``time_limit`` must
    degrade to a no-op there instead of raising ``ValueError``.
    """
    errors: list[BaseException] = []

    def worker():
        try:
            with time_limit(5):
                _ = sum(range(1000))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert errors == []


def test_time_limit_main_thread_no_error():
    with time_limit(5):
        _ = sum(range(1000))


def test_sector_analysis_keys_present():
    # Build a dataset with 1 ticker per sector
    from config import SECTORS
    sample = {ticker: [100.0, 110.0, 120.0] for tickers in SECTORS.values()
              for ticker in tickers[:1]}
    data = _make_prices(sample)
    prices, _, _, _ = calc_returns(data)
    total, vol, df = sector_analysis(prices)
    assert set(total.index) == set(SECTORS.keys())
    assert df.shape == (3, 8)
