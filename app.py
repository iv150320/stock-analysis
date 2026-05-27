import os
import time
from flask import Flask, render_template, request, send_from_directory

app = Flask(__name__)
app.secret_key = "cs50-final-project"
app.jinja_env.filters["basename"] = lambda p: os.path.basename(p) if p else ""

CHARTS_DIR = os.path.join(os.path.dirname(__file__), "charts")
CACHE_DURATION = 300
_cache = {}

from project import SECTORS, run_analysis, plot_price_with_ma


def cached_analysis(**kwargs):
    key = str(sorted(kwargs.items()))
    now = time.time()
    entry = _cache.get(key)
    if entry and (now - entry["time"]) < CACHE_DURATION:
        return entry["result"], entry["error"]
    result, error = run_analysis(**kwargs)
    _cache[key] = {"result": result, "error": error, "time": now}
    return result, error


@app.route("/health")
def health():
    return "ok", 200


@app.route("/")
def index():
    result, error = cached_analysis(period="1y", output_dir=CHARTS_DIR)
    data = format_result(result, "Full S&P 500")
    return render_template("index.html", **data, sectors=list(SECTORS.keys()))


@app.route("/charts/<path:filename>")
def chart_file(filename):
    return send_from_directory(CHARTS_DIR, filename)


@app.route("/sector", methods=["GET", "POST"])
def sector():
    sector_name = request.form.get("sector") if request.method == "POST" else request.args.get("name")
    period = request.form.get("period", "1y") if request.method == "POST" else "1y"

    if not sector_name or sector_name not in SECTORS:
        return render_template("sector.html", sectors=list(SECTORS.keys()),
                               sector_name=None, stocks=[], error="Select a sector.")

    result, error = cached_analysis(sector=sector_name, period=period, output_dir=CHARTS_DIR)
    if error:
        return render_template("sector.html", sectors=list(SECTORS.keys()),
                               sector_name=sector_name, stocks=[], error=error)

    ticker_data = []
    tr = result["total_return"]
    vol = result["volatility"]
    for t in result["tickers"]:
        if t in tr.index and t in vol.index:
            ticker_data.append({
                "symbol": t,
                "return": f"{tr[t] * 100:+.2f}%",
                "volatility": f"{vol[t] * 100:.2f}%",
            })
    ticker_data.sort(key=lambda x: float(x["return"].rstrip("%")), reverse=True)

    charts = result["charts"]
    for price_ticker in result["tickers"]:
        if price_ticker in result["prices"].columns:
            ma_path = plot_price_with_ma(result["prices"], price_ticker, CHARTS_DIR)
            if ma_path:
                charts[price_ticker] = os.path.basename(ma_path)

    return render_template("sector.html", sectors=list(SECTORS.keys()),
                           sector_name=sector_name, stocks=ticker_data,
                           charts=result["charts"], period=period)


@app.route("/stock", methods=["GET", "POST"])
def stock():
    symbol = request.form.get("symbol", "").upper() if request.method == "POST" else ""
    period = request.form.get("period", "1y") if request.method == "POST" else "1y"

    if not symbol:
        return render_template("stock.html", symbol=None)

    result, error = cached_analysis(tickers=[symbol], period=period, output_dir=CHARTS_DIR)
    if error:
        return render_template("stock.html", symbol=symbol, error=error)

    tr = result["total_return"]
    vol = result["volatility"]
    stock_data = {
        "symbol": symbol,
        "return": f"{tr[symbol] * 100:+.2f}%" if symbol in tr else "N/A",
        "volatility": f"{vol[symbol] * 100:.2f}%" if symbol in vol else "N/A",
    }

    charts = result["charts"]
    if symbol in result["prices"].columns:
        ma_path = plot_price_with_ma(result["prices"], symbol, CHARTS_DIR)
        if ma_path:
            charts["ma"] = os.path.basename(ma_path)

    return render_template("stock.html", symbol=symbol, stock=stock_data,
                           charts=charts, period=period)


def format_result(result, title):
    if result is None:
        return {"title": title, "error": True}
    tr = result["total_return"]
    vol = result["volatility"]
    sector_ret = result["sector_ret"]

    best = {}
    for t, v in tr.sort_values(ascending=False).head(5).items():
        best[t] = f"{v * 100:+.2f}%"
    worst = {}
    for t, v in tr.sort_values(ascending=False).tail(5).items():
        worst[t] = f"{v * 100:+.2f}%"

    sectors_data = {}
    for s in sector_ret.sort_values(ascending=False).index:
        sectors_data[s] = {
            "return": f"{sector_ret[s] * 100:+.2f}%",
            "volatility": f"{result['sector_vol'][s] * 100:.2f}%",
        }

    top_vol = {}
    for t, v in vol.sort_values(ascending=False).head(5).items():
        top_vol[t] = f"{v * 100:.2f}%"

    n_up = int((tr > 0).sum())
    n_down = int((tr <= 0).sum())
    avg_ret = f"{tr.mean() * 100:+.2f}%"
    avg_vol = f"{vol.mean() * 100:.2f}%"

    return {
        "title": title,
        "best": best,
        "worst": worst,
        "sectors_data": sectors_data,
        "top_vol": top_vol,
        "n_up": n_up,
        "n_down": n_down,
        "avg_ret": avg_ret,
        "avg_vol": avg_vol,
        "charts": result["charts"],
    }


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
