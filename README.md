# S&P 500 Stock Analysis Tool

#### Video Demo: https://youtu.be/PLACEHOLDER

#### Description:

A stock market analysis tool for the S&P 500 that provides both a **command-line interface** and a **Flask web dashboard**. It fetches real-time data via the Yahoo Finance API and produces comprehensive analysis reports, interactive tables, and chart visualizations across 160+ stocks in 8 sectors.

## Features

- **Dual Interface**: CLI for quick reports + Flask web dashboard for interactive exploration
- **Stock Universe**: 160 major S&P 500 stocks across 8 sectors
- **Web Dashboard**:
  - Market overview with summary statistics (avg return, volatility, breadth)
  - Sector breakdown tables and comparison charts
  - Individual stock lookup with moving average charts
  - Period selection (1mo, 3mo, 6mo, 1y, 2y)
- **Analysis Metrics**:
  - Total return over any period
  - Annualized volatility
  - Best/worst performers
  - Sector performance comparison
  - Inter-sector correlation
  - Market breadth (% of stocks positive)
- **Visualizations** (auto-generated PNG charts):
  - Top/bottom performers bar chart
  - Sector performance and volatility
  - Correlation heatmap
  - Volatility ranking
  - Price with 50/200-day moving averages

## Usage

### Web Interface
```bash
python app.py
# Open http://localhost:5000
```

### Command Line
```bash
python project.py --period 1y
python project.py --sector Technology --period 3mo
python project.py --ticker AAPL --period 6mo --all-charts
python project.py --period 1mo --no-charts
```

### CLI Arguments
| Argument | Description | Default |
|----------|-------------|---------|
| `--period` | Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, max) | `1y` |
| `--sector` | Sector name | all sectors |
| `--ticker` | Single stock symbol | all stocks |
| `--output` | Charts output directory | `charts` |
| `--all-charts` | Generate all MA charts | off |
| `--no-charts` | Text report only | off |

## Implementation

### Libraries
- **yfinance**: Fetches historical stock prices from Yahoo Finance
- **pandas/numpy**: Data manipulation, return/volatility calculations
- **matplotlib/seaborn**: Chart generation (bar charts, heatmaps, line plots)
- **Flask**: Web application framework

### Code Structure
| File | Purpose |
|------|---------|
| `project.py` | Analysis engine — data fetching, calculations, charting, CLI |
| `app.py` | Flask web app — routes, templates, rendering |
| `templates/` | HTML templates (Bootstrap 5) |
| `requirements.txt` | Python dependencies |

### Key Functions
- `fetch_data()` — Downloads prices via yfinance, handles single/multi-ticker column formats
- `calc_returns()` — Computes returns, total return %, annualized volatility
- `sector_analysis()` — Averages prices within each sector for sector metrics
- `plot_*()` — Generates matplotlib/seaborn charts, saved as PNG
- `run_analysis()` — Orchestrates the full pipeline, used by both CLI and web
- Flask routes — `/` dashboard, `/sector` sector view, `/stock` single stock lookup
