"""StockScope analysis engine.

Pure data layer: fetching prices via yfinance, computing returns/volatility,
and aggregating by sector.  No web / Flask concerns — those live in ``app.py``.

The CLI in :func:`main` is preserved so ``python project.py …`` still works
for offline report generation and is convenient for the CS50x video demo.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from contextlib import contextmanager
from datetime import datetime  # noqa: F401  (kept for backwards compatibility)

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
import yfinance as yf

from config import (
    DEFAULT_PERIOD,
    DEFAULT_TICKERS,
    PERIODS,
    SECTORS,
    TRADING_DAYS_PER_YEAR,
    YFINANCE_TIMEOUT,
    get_default_tickers,
    is_valid_period,
)

# SIGALRM is POSIX-only and can only be armed from the main thread.  Detect
# support once so :func:`time_limit` can degrade to a no-op elsewhere (e.g.
# Windows, or a WSGI server that handles requests off the main thread).
_HAS_SIGALRM = hasattr(signal, "SIGALRM")

sns.set_theme(style="whitegrid")


__all__ = [
    "SECTORS",
    "DEFAULT_TICKERS",
    "fetch_data",
    "calc_returns",
    "top_performers",
    "sector_analysis",
    "run_analysis",
    "print_report",
]


# ---------------------------------------------------------------------------
# Timeout helper (POSIX)
# ---------------------------------------------------------------------------

class TimeoutError(Exception):
    """Raised when an operation exceeds its wall-clock budget."""


@contextmanager
def time_limit(seconds: int):
    """Bound a block to ``seconds`` of wall-clock time (POSIX main thread).

    Used to bound ``yf.download()`` calls so a hung socket doesn't block
    the Gunicorn worker.  Where ``SIGALRM`` is unavailable (Windows) or the
    handler can't be armed (not the main thread), this degrades gracefully
    to a no-op rather than raising ``ValueError``/``AttributeError``.
    """
    def _handler(signum, frame):  # noqa: ANN001
        raise TimeoutError(f"operation timed out after {seconds}s")

    if not _HAS_SIGALRM:
        yield
        return

    try:
        old = signal.signal(signal.SIGALRM, _handler)
    except ValueError:
        # Not running in the main thread — can't install a signal handler.
        yield
        return

    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def fetch_data(tickers: list[str], period: str = DEFAULT_PERIOD) -> pd.DataFrame:
    """Download adjusted close prices for *tickers* over *period*.

    Returns a ``DataFrame`` whose columns are a ``MultiIndex`` of the form
    ``(Price level, Ticker)`` — this matches the contract used by
    :func:`calc_returns` below.
    """
    print(f"Fetching data for {len(tickers)} tickers...", file=sys.stderr)
    try:
        with time_limit(YFINANCE_TIMEOUT):
            data = yf.download(
                tickers,
                period=period,
                auto_adjust=True,
                progress=False,
                threads=True,
            )
    except TimeoutError as exc:
        print(f"yfinance timed out: {exc}", file=sys.stderr)
        return pd.DataFrame()
    except Exception as exc:  # noqa: BLE001
        print(f"yfinance download error: {exc}", file=sys.stderr)
        return pd.DataFrame()

    if data.empty:
        return data

    # When only one ticker is requested, yfinance returns flat columns.
    # Normalise so calc_returns can always do data.xs("Close", axis=1, …).
    if not isinstance(data.columns, pd.MultiIndex):
        ticker = tickers[0] if tickers else "?"
        data.columns = pd.MultiIndex.from_product([[ticker], data.columns])

    return data


def calc_returns(data: pd.DataFrame):
    """Derive ``(prices, returns, total_return, volatility)`` from raw data.

    * ``prices``        — wide ``DataFrame`` of close prices, one col/ticker
    * ``returns``       — daily percentage changes
    * ``total_return``  — period return per ticker
    * ``volatility``    — annualised standard deviation of daily returns
    """
    if data.empty:
        empty = pd.Series(dtype=float)
        return data, empty, empty, empty

    prices = data.xs("Close", axis=1, level="Price")
    clean = prices.ffill()
    returns = clean.pct_change()  # pandas >=2.0: `fill_method` arg is gone
    first, last = clean.iloc[0], clean.iloc[-1]
    total_return = (last - first) / first
    volatility = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    return prices, returns, total_return, volatility


def top_performers(total_return: pd.Series, n: int = 10):
    """Return ``(best, worst)`` — both already sorted desc by return."""
    ordered = total_return.dropna().sort_values(ascending=False)
    best = ordered.head(n)
    worst = ordered.tail(n).sort_values(ascending=False)
    return best, worst


def sector_analysis(prices: pd.DataFrame):
    """Mean constituent price per sector.

    Returns ``(total, vol, sector_df)``.  ``total`` / ``vol`` are
    ``pd.Series`` indexed by sector name.
    """
    sector_map: dict[str, pd.Series] = {}
    for sector, tickers in SECTORS.items():
        valid = [t for t in tickers if t in prices.columns]
        if valid:
            sector_map[sector] = prices[valid].mean(axis=1)

    sector_df = pd.DataFrame(sector_map)
    sector_returns = sector_df.ffill().pct_change()
    total = (sector_df.ffill().iloc[-1] - sector_df.ffill().iloc[0]) / sector_df.ffill().iloc[0]
    vol = sector_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    return total, vol, sector_df


# ---------------------------------------------------------------------------
# Plot helpers (CLI only — the web app uses Chart.js)
# ---------------------------------------------------------------------------

def plot_top_performers(best: pd.Series, worst: pd.Series, output_dir: str) -> str | None:
    if best.empty and worst.empty:
        return None
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    colors_best = ["#2ecc71" if v > 0 else "#e74c3c" for v in best.values]
    colors_worst = ["#2ecc71" if v > 0 else "#e74c3c" for v in worst.values]

    ax1.barh(range(len(best)), best.values * 100, color=colors_best)
    ax1.set_yticks(range(len(best)))
    ax1.set_yticklabels(best.index)
    ax1.set_xlabel("Total Return (%)")
    ax1.set_title("Top 10 Best Performers")
    ax1.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax1.invert_yaxis()

    ax2.barh(range(len(worst)), worst.values * 100, color=colors_worst)
    ax2.set_yticks(range(len(worst)))
    ax2.set_yticklabels(worst.index)
    ax2.set_xlabel("Total Return (%)")
    ax2.set_title("Top 10 Worst Performers")
    ax2.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax2.invert_yaxis()

    plt.tight_layout()
    path = os.path.join(output_dir, "top_performers.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved {path}")
    return path


def plot_sector_performance(sector_ret, sector_vol, output_dir: str) -> str | None:
    if sector_ret.empty:
        return None
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    colors = ["#2ecc71" if v > 0 else "#e74c3c" for v in sector_ret.values]
    ax1.barh(range(len(sector_ret)), sector_ret.values * 100, color=colors)
    ax1.set_yticks(range(len(sector_ret)))
    ax1.set_yticklabels(sector_ret.index)
    ax1.set_xlabel("Total Return (%)")
    ax1.set_title("Sector Performance")
    ax1.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax1.invert_yaxis()

    ax2.barh(range(len(sector_vol)), sector_vol.values * 100, color="#3498db")
    ax2.set_yticks(range(len(sector_vol)))
    ax2.set_yticklabels(sector_vol.index)
    ax2.set_xlabel("Annualized Volatility (%)")
    ax2.set_title("Sector Volatility")
    ax2.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax2.invert_yaxis()

    plt.tight_layout()
    path = os.path.join(output_dir, "sector_performance.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved {path}")
    return path


def plot_correlation_heatmap(sector_df, output_dir: str) -> str | None:
    if sector_df.empty or sector_df.shape[1] < 2:
        return None
    corr = sector_df.ffill().pct_change().corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    sns.heatmap(corr, mask=mask, annot=True, fmt=".2f", cmap="RdBu_r",
                vmin=-1, vmax=1, center=0, square=True,
                linewidths=0.5, ax=ax)
    ax.set_title("Sector Return Correlation")
    plt.tight_layout()
    path = os.path.join(output_dir, "correlation_heatmap.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved {path}")
    return path


def plot_price_with_ma(prices, ticker: str, output_dir: str) -> str | None:
    if ticker not in prices.columns:
        print(f"{ticker} not found in data", file=sys.stderr)
        return None

    fig, ax = plt.subplots(figsize=(12, 5))
    prices[ticker].plot(ax=ax, label="Close", color="#2c3e50", linewidth=1)
    prices[ticker].rolling(50).mean().plot(ax=ax, label="50-day MA", color="#e74c3c")
    prices[ticker].rolling(200).mean().plot(ax=ax, label="200-day MA", color="#2980b9")
    ax.set_title(f"{ticker} Price with Moving Averages")
    ax.set_ylabel("Price ($)")
    ax.legend()
    plt.tight_layout()
    path = os.path.join(output_dir, f"{ticker}_ma.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved {path}")
    return path


def plot_volatility(volatility: pd.Series, output_dir: str, n: int = 20) -> str | None:
    if volatility.empty:
        return None
    top_vol = volatility.sort_values(ascending=False).head(n)

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = plt.cm.Reds(np.linspace(0.3, 0.9, n))
    ax.barh(range(len(top_vol)), top_vol.values * 100, color=colors)
    ax.set_yticks(range(len(top_vol)))
    ax.set_yticklabels(top_vol.index)
    ax.set_xlabel("Annualized Volatility (%)")
    ax.set_title(f"Top {n} Most Volatile Stocks")
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax.invert_yaxis()
    plt.tight_layout()
    path = os.path.join(output_dir, "volatility.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved {path}")
    return path


def print_report(total_return, volatility, sector_ret, sector_vol, period):
    print("\n" + "=" * 70)
    print(f"  S&P 500 STOCK ANALYSIS REPORT ({period})")
    print("=" * 70)

    print("\nTop 5 Best Performers:")
    best = total_return.sort_values(ascending=False).head(5)
    for ticker, ret in best.items():
        print(f"  {ticker:>6s}: {ret * 100:>+6.2f}%")

    print("\nTop 5 Worst Performers:")
    worst = total_return.sort_values(ascending=True).head(5)
    for ticker, ret in worst.items():
        print(f"  {ticker:>6s}: {ret * 100:>+6.2f}%")

    print("\nSector Performance:")
    for sector in sector_ret.sort_values(ascending=False).index:
        r = sector_ret[sector] * 100
        v = sector_vol[sector] * 100
        print(f"  {sector:<20s}: {r:>+6.2f}%  (volatility: {v:>5.2f}%)")

    print("\nMost Volatile Stocks (Top 5):")
    top_vol = volatility.sort_values(ascending=False).head(5)
    for ticker, vol_v in top_vol.items():
        print(f"  {ticker:>6s}: {vol_v * 100:>5.2f}%")

    print("\nLeast Volatile Stocks (Top 5):")
    bottom_vol = volatility.sort_values(ascending=True).head(5)
    for ticker, vol_v in bottom_vol.items():
        print(f"  {ticker:>6s}: {vol_v * 100:>5.2f}%")

    market_avg_ret = total_return.mean() * 100
    market_avg_vol = volatility.mean() * 100
    print("\nMarket Average:")
    print(f"  Average Return:  {market_avg_ret:>+6.2f}%")
    print(f"  Average Volatility: {market_avg_vol:>5.2f}%")

    n_positive = int((total_return > 0).sum())
    n_negative = int((total_return <= 0).sum())
    total_count = n_positive + n_negative
    print("\nBreadth:")
    print(f"  Stocks Up:    {n_positive}")
    print(f"  Stocks Down:  {n_negative}")
    if total_count:
        print(f"  {n_positive / total_count * 100:>5.1f}% of stocks positive")
    print("=" * 70)
    print()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_analysis(
    tickers: list[str] | None = None,
    sector: str | None = None,
    period: str = DEFAULT_PERIOD,
    output_dir: str = "charts",
    generate_charts: bool = True,
):
    """Run the full analysis pipeline.  Returns ``(result_dict, error_str)``."""
    if tickers:
        pass
    elif sector:
        if sector not in SECTORS:
            return None, f"Unknown sector: {sector}"
        tickers = SECTORS[sector]
    else:
        tickers = get_default_tickers()

    os.makedirs(output_dir, exist_ok=True)

    data = fetch_data(tickers, period)
    if data.empty:
        return None, "No data fetched. Check ticker symbols or internet connection."

    prices, _, total_return, volatility = calc_returns(data)
    total_return = total_return.dropna()
    volatility = volatility.dropna()

    sector_ret, sector_vol, sector_df = sector_analysis(prices)

    charts: dict = {}
    if generate_charts:
        top_best, top_worst = top_performers(total_return)
        charts["top_performers"] = plot_top_performers(top_best, top_worst, output_dir)
        charts["sector_performance"] = plot_sector_performance(sector_ret, sector_vol, output_dir)
        charts["correlation_heatmap"] = plot_correlation_heatmap(sector_df, output_dir)
        charts["volatility"] = plot_volatility(volatility, output_dir)

    result = {
        "total_return": total_return,
        "volatility": volatility,
        "sector_ret": sector_ret,
        "sector_vol": sector_vol,
        "prices": prices,
        "charts": charts,
        "tickers": tickers,
    }
    return result, None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="S&P 500 Stock Analysis Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python project.py --period 6mo
  python project.py --sector Technology --period 1y
  python project.py --ticker AAPL --period 3mo
  python project.py --all-charts
        """,
    )
    parser.add_argument("--period", default=DEFAULT_PERIOD,
                        help=f"Data period; one of: {', '.join(PERIODS)}")
    parser.add_argument("--sector", help=f"Analyze a specific sector: {', '.join(SECTORS.keys())}")
    parser.add_argument("--ticker", help="Analyze a single ticker")
    parser.add_argument("--output", default="charts", help="Output directory for charts")
    parser.add_argument("--all-charts", action="store_true", help="Generate all chart types")
    parser.add_argument("--no-charts", action="store_true", help="Skip chart generation")
    args = parser.parse_args()

    if not is_valid_period(args.period):
        print(
            f"Invalid period: {args.period}. Choose one of: {', '.join(PERIODS)}",
            file=sys.stderr,
        )
        sys.exit(1)

    tickers = None
    if args.ticker:
        tickers = [args.ticker.upper()]
    elif args.sector:
        if args.sector not in SECTORS:
            print(f"Unknown sector: {args.sector}", file=sys.stderr)
            sys.exit(1)

    result, error = run_analysis(
        tickers=tickers,
        sector=args.sector,
        period=args.period,
        output_dir=args.output,
        generate_charts=not args.no_charts,
    )
    if error:
        print(error, file=sys.stderr)
        sys.exit(1)

    total_return = result["total_return"]
    volatility = result["volatility"]
    sector_ret = result["sector_ret"]
    sector_vol = result["sector_vol"]
    prices = result["prices"]

    print_report(total_return, volatility, sector_ret, sector_vol, args.period)

    if args.all_charts and args.ticker:
        plot_price_with_ma(prices, args.ticker, args.output)
    elif args.all_charts and args.sector:
        for ticker in SECTORS[args.sector]:
            plot_price_with_ma(prices, ticker, args.output)
    elif args.all_charts:
        for sector_name, tickers_list in SECTORS.items():
            for ticker in tickers_list:
                if ticker in prices.columns:
                    plot_price_with_ma(prices, ticker, args.output)

    print(f"Charts saved to: {os.path.abspath(args.output)}/")


if __name__ == "__main__":
    main()
