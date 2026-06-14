# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CI workflow badge, Codecov integration, and `pytest -v --tb=short` output.
- `CHANGELOG.md` in Keep-a-Changelog format.
- `Makefile` with `install`, `test`, `run`, `docker`, `deploy`, and `clean` targets.
- GitHub issue templates (bug report, feature request) and pull-request template.
- `docs/banner.svg` for README hero section.

### Changed
- `.github/workflows/ci.yml` trigger: removed redundant `push` to `main` (deploy workflow already covers push-to-main testing).

---

## [1.0.0] — 2026-06-13

### Added
- **Dashboard** (`/`): market-wide overview with sector performance, market breadth (up/down), top/bottom performers, and volatility ranking.
- **Sector drill-down** (`/sector`): per-sector analysis with constituent returns, risk×return scatter plot, and period selection (1mo–2y).
- **Stock lookup** (`/stock`): single-ticker price history with 50-day and 200-day simple moving averages.
- **Dark / Light theme toggle**: `data-theme`-driven CSS variables with live chart re-painting.
- **Mobile-first responsive design**: hamburger nav, fluid `clamp()` typography, touch-friendly tap targets.
- **TTL + LRU in-memory cache**: 300-second TTL, 128-entry LRU bound. Cold yfinance requests (~10 s for 160 tickers) are cached; subsequent hits return in < 20 ms.
- **SIGALRM watchdog** on `yf.download`: 30-second timeout prevents Gunicorn worker hangs.
- **Self-hosted front-end assets**: Chart.js 4.4.7, Bootstrap 5.3.3, and FontAwesome vendored under `static/` — no CDN dependency.
- **Docker production image**: `python:3.10-slim` base, Gunicorn with 2 workers, healthcheck probe.
- **GitHub Actions CI/CD**: pytest matrix (Python 3.10, 3.12) → Docker build → push to GHCR → SSH deploy to VPS.
- **CLI mode** (`project.py --period --sector --ticker --output`): offline report generation with optional PNG chart export.
- **24 unit tests** covering `calc_returns`, `top_performers`, `sector_analysis`, `TTLCache`, `safe_round`, `normalise_period`, and `mean_ignore_none`.
- **Period whitelist validation**: server-side coercion of unknown periods to the default (`1y`).

### Security
- Default secret key warning when `STOCKSCOPE_SECRET_KEY` is unset in production.
- Cache bounds prevent unbounded memory growth.
- Input sanitization on ticker symbols and period parameters.

---

## [0.9.0] — 2026-06-10

### Added
- Initial CS50x final project scaffold (Flask + Jinja2 + yfinance).
- Basic `/` route with hardcoded S&P 500 sector data.
- `config.py` with 8 sectors and 20 tickers each (160 total).

---

[Unreleased]: https://github.com/iv150320/stock-analysis/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/iv150320/stock-analysis/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/iv150320/stock-analysis/releases/tag/v0.9.0