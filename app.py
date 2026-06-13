"""StockScope Flask web application.

Routes:
    GET  /              Market-wide dashboard
    GET  /sector        Per-sector analysis (form-driven, GET or POST)
    GET  /stock         Single-stock detail (form-driven, GET or POST)
    GET  /health        Health probe (used by Docker / CI)

A simple TTL+LRU cache wraps :func:`run_analysis` so we don't hammer
yfinance on every page reload while still picking up new data every
``STOCKSCOPE_CACHE_TTL`` seconds (default 5 minutes).
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from typing import Any, Callable, TypeVar

import pandas as pd
from flask import Flask, render_template, request

from config import (
    DEBUG,
    HOST,
    PORT,
    SECRET_KEY,
    SECTORS,
    CACHE_DURATION,
    CACHE_MAX_ENTRIES,
    DEFAULT_PERIOD,
    is_valid_period,
)
from project import run_analysis


T = TypeVar("T")


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ---------------------------------------------------------------------------
# TTL + LRU cache
# ---------------------------------------------------------------------------

class TTLCache:
    """Tiny ordered-dict cache: O(1) get/set, evicts oldest past max size,
    expires entries after ``ttl`` seconds.
    """

    def __init__(self, max_size: int, ttl: int) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self.max_size = max_size
        self.ttl = ttl
        self._data: "OrderedDict[str, tuple[float, T]]" = OrderedDict()

    def get(self, key: str) -> T | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        ts, value = entry
        if (time.time() - ts) >= self.ttl:
            self._data.pop(key, None)
            return None
        # mark as recently used
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: T) -> None:
        self._data[key] = (time.time(), value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)


_cache = TTLCache(max_size=CACHE_MAX_ENTRIES, ttl=CACHE_DURATION)


def cached_analysis(**kwargs) -> tuple[Any | None, str | None]:
    """Memoised wrapper around :func:`run_analysis`.

    Cache key is the sorted, stringified kwargs so the *same* query
    (sector="Energy", period="1y") returns the same result within ``ttl``.
    """
    key = json.dumps(kwargs, sort_keys=True, default=str)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    # Matplotlib PNGs are only used by the CLI; the web UI renders via Chart.js,
    # so we save cycles and the bind-mounted volume by skipping them entirely.
    result, error = run_analysis(generate_charts=False, **kwargs)
    if result is not None:
        _cache.set(key, (result, error))
    return result, error


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def to_json(obj: Any) -> str:
    """Compact JSON serialiser for embedding data into a `<script>` block."""
    return json.dumps(obj, default=str)


def safe_round(value: Any, ndigits: int = 2) -> float | None:
    """Round *value* if it's numeric; return ``None`` for NaN/None."""
    if value is None:
        return None
    try:
        out = round(float(value), ndigits)
    except (TypeError, ValueError):
        return None
    return out


def normalise_period(raw: str | None) -> str:
    """Reject unknown periods; fall back to default rather than crashing."""
    return raw if raw and is_valid_period(raw) else DEFAULT_PERIOD


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health")
def health() -> tuple[str, int]:
    return "ok", 200


@app.route("/")
def index():
    result, error = cached_analysis(period=DEFAULT_PERIOD)
    if error or result is None:
        return render_template("index.html", error=error or "Analysis failed")

    tr = result["total_return"]
    vol = result["volatility"]
    sector_ret = result["sector_ret"]
    sector_vol = result["sector_vol"]

    n_up = int((tr > 0).sum())
    n_down = int((tr <= 0).sum())
    avg_ret = safe_round(tr.mean() * 100)
    avg_vol = safe_round(vol.mean() * 100)

    sorted_desc = tr.sort_values(ascending=False)
    top5 = [(t, safe_round(tr[t] * 100)) for t in sorted_desc.head(5).index]
    # Bug fix: was `sort_values(ascending=False).tail(5)` which gives the
    # 5 lowest returns in ascending order — the wrong way around.
    sort_asc = tr.sort_values(ascending=True)
    bot5 = [(t, safe_round(tr[t] * 100)) for t in sort_asc.head(5).index]

    top_vol5 = [(t, safe_round(vol[t] * 100)) for t in vol.sort_values(ascending=False).head(5).index]

    sectors_list = []
    for s in sector_ret.sort_values(ascending=False).index:
        sectors_list.append({
            "name": s,
            "return": safe_round(sector_ret[s] * 100),
            "volatility": safe_round(sector_vol[s] * 100),
        })

    return render_template(
        "index.html",
        n_up=n_up, n_down=n_down,
        avg_ret=avg_ret, avg_vol=avg_vol,
        top5=top5, bot5=bot5, top_vol5=top_vol5,
        sectors=sectors_list,
        sector_labels=to_json([s["name"] for s in sectors_list]),
        sector_returns=to_json([s["return"] for s in sectors_list]),
        sector_vols=to_json([s["volatility"] for s in sectors_list]),
        perf_labels=to_json([t for t, _ in top5]),
        perf_values=to_json([v for _, v in top5]),
        perf_bot_labels=to_json([t for t, _ in bot5]),
        perf_bot_values=to_json([v for _, v in bot5]),
        vol_labels=to_json([t for t, _ in top_vol5]),
        vol_values=to_json([v for _, v in top_vol5]),
    )


@app.route("/sector", methods=["GET", "POST"])
def sector():
    if request.method == "POST":
        sector_name = request.form.get("sector") or ""
        period = normalise_period(request.form.get("period"))
    else:
        sector_name = request.args.get("name") or ""
        period = normalise_period(request.args.get("period"))

    if not sector_name or sector_name not in SECTORS:
        return render_template(
            "sector.html",
            sectors=list(SECTORS.keys()),
            sector_name=None,
            stocks=[],
            period=period,
        )

    result, error = cached_analysis(sector=sector_name, period=period)
    if error or result is None:
        return render_template(
            "sector.html",
            sectors=list(SECTORS.keys()),
            sector_name=sector_name,
            stocks=[],
            error=error,
            period=period,
        )

    tr = result["total_return"]
    vol = result["volatility"]

    stocks_list = []
    for ticker in result["tickers"]:
        if ticker in tr.index and ticker in vol.index:
            stocks_list.append({
                "symbol": ticker,
                "return": safe_round(tr[ticker] * 100),
                "volatility": safe_round(vol[ticker] * 100),
            })
    stocks_list.sort(key=lambda x: (x["return"] is None, -(x["return"] or 0.0)))

    avg_ret = (
        round(sum(s["return"] for s in stocks_list) / len(stocks_list), 2)
        if stocks_list else 0
    )
    avg_vol = (
        round(sum(s["volatility"] for s in stocks_list) / len(stocks_list), 2)
        if stocks_list else 0
    )

    return render_template(
        "sector.html",
        sectors=list(SECTORS.keys()),
        sector_name=sector_name,
        stocks=stocks_list,
        avg_ret=avg_ret, avg_vol=avg_vol,
        n_stocks=len(stocks_list),
        stock_labels=to_json([s["symbol"] for s in stocks_list]),
        stock_returns=to_json([s["return"] for s in stocks_list]),
        stock_vols=to_json([s["volatility"] for s in stocks_list]),
        period=period,
    )


@app.route("/stock", methods=["GET", "POST"])
def stock():
    if request.method == "POST":
        symbol = (request.form.get("symbol") or "").upper().strip()
        period = normalise_period(request.form.get("period"))
    else:
        # GET path — allow direct deep-links like /stock?symbol=AAPL&period=1y
        symbol = (request.args.get("symbol") or "").upper().strip()
        period = normalise_period(request.args.get("period"))

    if not symbol:
        return render_template("stock.html", symbol=None, period=period)

    result, error = cached_analysis(tickers=[symbol], period=period)
    if error or result is None:
        return render_template("stock.html", symbol=symbol, error=error,
                               period=period)

    tr = result["total_return"]
    vol = result["volatility"]
    prices = result["prices"]

    ret_val = safe_round(tr[symbol] * 100) if symbol in tr else None
    vol_val = safe_round(vol[symbol] * 100) if symbol in vol else None

    dates: list[str] = []
    close_prices: list[float] = []
    ma50: list[float | None] = []
    ma200: list[float | None] = []
    has_chart_data = False
    if symbol in prices.columns:
        series = prices[symbol].dropna()
        if len(series) > 0:
            has_chart_data = True
            dates = [str(d.date()) for d in series.index]
            close_prices = [safe_round(v) for v in series.values]
            ma50_raw = series.rolling(50).mean()
            ma200_raw = series.rolling(200).mean()
            ma50 = [safe_round(v) if not pd.isna(v) else None for v in ma50_raw.values]
            ma200 = [safe_round(v) if not pd.isna(v) else None for v in ma200_raw.values]

    # CRITICAL FIX: the chart block in stock.html is gated on `ret is not None`,
    # which silently hides the price chart whenever a fetch succeeds but the
    # symbol is missing from the result index.  Pass has_chart_data explicitly
    # so users always see the price line when we have it.
    return render_template(
        "stock.html",
        symbol=symbol,
        ret=ret_val,
        vol=vol_val,
        has_chart_data=has_chart_data,
        dates=to_json(dates),
        prices=to_json(close_prices),
        ma50=to_json(ma50),
        ma200=to_json(ma200),
        period=period,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=DEBUG, host=HOST, port=PORT)
