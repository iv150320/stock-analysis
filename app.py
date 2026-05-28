import json
import os
import time

import pandas as pd
from flask import Flask, render_template, request

app = Flask(__name__)
app.secret_key = "cs50-final-project"

CACHE_DURATION = 300
_cache = {}

from project import SECTORS, run_analysis


def cached_analysis(**kwargs):
    key = str(sorted(kwargs.items()))
    now = time.time()
    entry = _cache.get(key)
    if entry and (now - entry["time"]) < CACHE_DURATION:
        return entry["result"], entry["error"]
    result, error = run_analysis(**kwargs)
    _cache[key] = {"result": result, "error": error, "time": now}
    return result, error


def to_json(obj):
    return json.dumps(obj, default=str)


def np_val(v):
    return float(v) if hasattr(v, "item") else v


@app.route("/health")
def health():
    return "ok", 200


@app.route("/")
def index():
    result, error = cached_analysis(period="1y")
    if error or result is None:
        return render_template("index.html", error=error or "Analysis failed")

    tr = result["total_return"]
    vol = result["volatility"]
    sector_ret = result["sector_ret"]
    sector_vol = result["sector_vol"]

    n_up = int((tr > 0).sum())
    n_down = int((tr <= 0).sum())
    avg_ret = round(float(tr.mean() * 100), 2)
    avg_vol = round(float(vol.mean() * 100), 2)

    top5 = [(t, round(float(tr[t] * 100), 2)) for t in tr.sort_values(ascending=False).head(5).index]
    bot5 = [(t, round(float(tr[t] * 100), 2)) for t in tr.sort_values(ascending=False).tail(5).index]

    top_vol5 = [(t, round(float(vol[t] * 100), 2)) for t in vol.sort_values(ascending=False).head(5).index]

    sectors_list = []
    for s in sector_ret.sort_values(ascending=False).index:
        r = round(float(sector_ret[s] * 100), 2)
        v = round(float(sector_vol[s] * 100), 2)
        sectors_list.append({"name": s, "return": r, "volatility": v})

    return render_template("index.html",
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
        vol_values=to_json([v for _, v in top_vol5]))


@app.route("/sector", methods=["GET", "POST"])
def sector():
    if request.method == "POST":
        sector_name = request.form.get("sector")
        period = request.form.get("period", "1y")
    else:
        sector_name = request.args.get("name")
        period = request.args.get("period", "1y")

    if not sector_name or sector_name not in SECTORS:
        return render_template("sector.html", sectors=list(SECTORS.keys()),
            sector_name=None, stocks=[], period=period)

    result, error = cached_analysis(sector=sector_name, period=period)
    if error or result is None:
        return render_template("sector.html", sectors=list(SECTORS.keys()),
                               sector_name=sector_name, stocks=[], error=error)

    tr = result["total_return"]
    vol = result["volatility"]

    stocks_list = []
    for t in result["tickers"]:
        if t in tr.index and t in vol.index:
            stocks_list.append({
                "symbol": t,
                "return": round(float(tr[t] * 100), 2),
                "volatility": round(float(vol[t] * 100), 2),
            })
    stocks_list.sort(key=lambda x: x["return"], reverse=True)

    avg_ret = round(sum(s["return"] for s in stocks_list) / len(stocks_list), 2) if stocks_list else 0
    avg_vol = round(sum(s["volatility"] for s in stocks_list) / len(stocks_list), 2) if stocks_list else 0

    return render_template("sector.html",
                           sectors=list(SECTORS.keys()),
                           sector_name=sector_name,
                           stocks=stocks_list,
                           avg_ret=avg_ret, avg_vol=avg_vol,
                           n_stocks=len(stocks_list),
                           stock_labels=to_json([s["symbol"] for s in stocks_list]),
                           stock_returns=to_json([s["return"] for s in stocks_list]),
                           stock_vols=to_json([s["volatility"] for s in stocks_list]),
                           period=period)


@app.route("/stock", methods=["GET", "POST"])
def stock():
    symbol = request.form.get("symbol", "").upper() if request.method == "POST" else ""
    period = request.form.get("period", "1y") if request.method == "POST" else "1y"

    if not symbol:
        return render_template("stock.html", symbol=None, period="1y")

    result, error = cached_analysis(tickers=[symbol], period=period)
    if error or result is None:
        return render_template("stock.html", symbol=symbol, error=error)

    tr = result["total_return"]
    vol = result["volatility"]
    prices = result["prices"]

    ret_val = round(float(tr[symbol] * 100), 2) if symbol in tr else None
    vol_val = round(float(vol[symbol] * 100), 2) if symbol in vol else None

    dates = []
    close_prices = []
    ma50 = []
    ma200 = []
    if symbol in prices.columns:
        series = prices[symbol].dropna()
        dates = [str(d.date()) for d in series.index]
        close_prices = [round(float(v), 2) for v in series.values]
        ma50_raw = series.rolling(50).mean()
        ma200_raw = series.rolling(200).mean()
        ma50 = [round(float(v), 2) if not pd.isna(v) else None for v in ma50_raw.values]
        ma200 = [round(float(v), 2) if not pd.isna(v) else None for v in ma200_raw.values]

    return render_template("stock.html",
                           symbol=symbol, ret=ret_val, vol=vol_val,
                           dates=to_json(dates),
                           prices=to_json(close_prices),
                           ma50=to_json(ma50),
                           ma200=to_json(ma200),
                           period=period)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
