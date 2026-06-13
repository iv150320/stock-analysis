---
name: testing-stockscope
description: Set up and end-to-end test the StockScope S&P 500 dashboard (Flask web UI + CLI). Use when verifying changes to app.py, project.py, config.py, or the templates.
---

# Testing StockScope

StockScope is a CS50x project: a Flask web dashboard (`app.py`) + a CLI (`project.py`) over a shared analysis engine, pulling live prices from Yahoo Finance via `yfinance`.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

Run the web app (a SECRET_KEY is only needed to silence a warning; debug off is fine):

```bash
STOCKSCOPE_SECRET_KEY=local-test FLASK_DEBUG=0 python app.py   # serves http://localhost:5000
```

Health check: `curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/health` should return `200`.

## Network requirement

The app needs outbound access to Yahoo Finance (`yfinance`). If `fetch_data` returns empty, the box likely can't reach Yahoo — that's an environment issue, not a code bug. Quick check:
```bash
python -c "from project import fetch_data; print(fetch_data(['AAPL'], '6mo').shape)"
```

## UI flows to exercise (browser at http://localhost:5000)

1. **Dashboard `/`** — loads all 160 tickers. First (cold) load takes ~10-15s; results are cached ~300s (TTLCache), so warm it once with `curl http://localhost:5000/` before recording so the browser load is fast. Expect: heading "S&P 500 Market Dashboard", a sector bar chart, market-breadth donut, top/bottom performer + volatility bar charts, and numeric Avg Return / Avg Volatility (never `NaN`/`None`).
2. **Sectors `/sector`** — select a Market Sector + Analysis Period, click **Run Analytics**. Expect numeric **Avg Return** / **Avg Volatility** cards, a constituents bar chart, and a rankings table. Note: avg is a simple mean of per-ticker returns, so one outlier (e.g. MU) can pull the sector average very high — that's expected, not a bug.
3. **Stock `/stock`** — type a ticker (e.g. AAPL), pick a period, click **Analyze Stock**. Expect a price line chart with 50-day & 200-day SMA overlays (200-day may be empty for periods < ~1y) and numeric Total Return / Volatility cards.

Form field names: `/sector` uses `name="sector"` + `name="period"`; `/stock` uses `name="symbol"` + `name="period"`. Web routes fall back to `DEFAULT_PERIOD` for invalid periods (`normalise_period`).

## CLI checks (shell, non-interactive — no recording needed)

```bash
python project.py --period 1d                                   # rejected: exit 1, "Invalid period: 1d. Choose one of: ..."
python project.py --period 6mo --ticker AAPL --no-charts        # runs, exit 0, prints report
python -m pytest -q                                             # unit suite (all deterministic, no network)
```

Valid periods (single source of truth in `config.py` `PERIODS`): `5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max`.

## Notes

- The unit tests mock/avoid network, so `pytest` works offline; the web/CLI flows need Yahoo Finance access.
- There is no Vercel/Netlify-style preview deploy. Deployment is build → GHCR → SSH-to-VPS on merge to `main` (`.github/workflows/deploy.yml`). CI (`.github/workflows/ci.yml`) runs `pytest` on PRs across Python 3.10 + 3.12.

## Devin Secrets Needed

None. Local testing needs no secrets (`STOCKSCOPE_SECRET_KEY` can be any throwaway string for local runs). Yahoo Finance access is unauthenticated.
