import argparse
import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
import yfinance as yf

sns.set_theme(style="whitegrid")


SECTORS = {
    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "CRM", "ADBE", "ORCL", "QCOM", "AMD",
                   "INTC", "TXN", "CSCO", "IBM", "NOW", "AMAT", "MU", "ADI", "ADP", "FIS"],
    "Finance": ["JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "BLK", "SCHW", "USB",
                "PNC", "TFC", "BK", "COF", "SPGI", "MCO", "SIVBQ", "DFS", "MET", "AIG"],
    "Healthcare": ["UNH", "PFE", "ABBV", "MRK", "ABT", "LLY", "TMO", "JNJ", "BMY", "AMGN",
                   "CVS", "MDT", "ISRG", "SYK", "GILD", "BSX", "REGN", "VRTX", "DHR", "BDX"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "BKNG", "TGT", "TJX",
                          "ROST", "GM", "F", "EBAY", "MAR", "HLT", "DRI", "YUM", "CMG", "AZO"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "OXY", "MPC", "PSX", "VLO", "KMI",
               "HAL", "BKR", "DVN", "HES", "FANG", "MRO", "CTRA", "TRGP", "EQT", "WMB"],
    "Communication": ["GOOG", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "CHTR", "TMUS", "EA",
                      "TTWO", "WBD", "PARA", "OMC", "IPG", "NWSA", "FOXA", "LYV", "MTCH", "DISH"],
    "Industrials": ["CAT", "GE", "BA", "HON", "UNP", "UPS", "RTX", "LMT", "MMM", "GD",
                    "NOC", "CSX", "FDX", "DE", "CARR", "ETN", "EMR", "ITW", "PAYX", "PH"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "ED", "PEG",
                  "WEC", "AWK", "ES", "DTE", "AEE", "CNP", "EIX", "FE", "CMS", "ATO"],
}

DEFAULT_TICKERS = [t for sector in SECTORS.values() for t in sector]


def fetch_data(tickers, period="1y"):
    print(f"Fetching data for {len(tickers)} tickers...", file=sys.stderr)
    data = yf.download(tickers, period=period, auto_adjust=True, progress=False)
    if data.empty:
        return data
    if not isinstance(data.columns, pd.MultiIndex):
        ticker = tickers[0] if tickers else "?"
        data.columns = pd.MultiIndex.from_product([[ticker], data.columns])
    return data


def calc_returns(data):
    prices = data.xs("Close", axis=1, level="Price")
    returns = prices.ffill().pct_change(fill_method=None)
    total_return = (prices.ffill().iloc[-1] - prices.ffill().iloc[0]) / prices.ffill().iloc[0]
    volatility = returns.std() * np.sqrt(252)
    return prices, returns, total_return, volatility


def top_performers(total_return, n=10):
    sorted_ret = total_return.sort_values(ascending=False)
    best = sorted_ret.head(n)
    worst = sorted_ret.tail(n)
    return best, worst


def plot_top_performers(best, worst, output_dir):
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


def sector_analysis(prices):
    sector_map = {}
    for sector, tickers in SECTORS.items():
        valid = [t for t in tickers if t in prices.columns]
        if valid:
            sector_map[sector] = prices[valid].mean(axis=1)

    sector_df = pd.DataFrame(sector_map)
    sector_returns = sector_df.ffill().pct_change()
    total = (sector_df.ffill().iloc[-1] - sector_df.ffill().iloc[0]) / sector_df.ffill().iloc[0]
    vol = sector_returns.std() * np.sqrt(252)
    return total, vol, sector_df


def plot_sector_performance(sector_ret, sector_vol, output_dir):
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


def plot_correlation_heatmap(sector_df, output_dir):
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


def plot_price_with_ma(prices, ticker, output_dir):
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


def plot_volatility(volatility, output_dir, n=20):
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

    print(f"\nTop 5 Best Performers:")
    best = total_return.sort_values(ascending=False).head(5)
    for ticker, ret in best.items():
        print(f"  {ticker:>6s}: {ret * 100:>+6.2f}%")

    print(f"\nTop 5 Worst Performers:")
    worst = total_return.sort_values(ascending=False).tail(5)
    for ticker, ret in worst.items():
        print(f"  {ticker:>6s}: {ret * 100:>+6.2f}%")

    print(f"\nSector Performance:")
    for sector in sector_ret.sort_values(ascending=False).index:
        r = sector_ret[sector] * 100
        v = sector_vol[sector] * 100
        print(f"  {sector:<20s}: {r:>+6.2f}%  (volatility: {v:>5.2f}%)")

    print(f"\nMost Volatile Stocks (Top 5):")
    top_vol = volatility.sort_values(ascending=False).head(5)
    for ticker, vol in top_vol.items():
        print(f"  {ticker:>6s}: {vol * 100:>5.2f}%")

    print(f"\nLeast Volatile Stocks (Top 5):")
    bottom_vol = volatility.sort_values(ascending=True).head(5)
    for ticker, vol in bottom_vol.items():
        print(f"  {ticker:>6s}: {vol * 100:>5.2f}%")

    market_avg_ret = total_return.mean() * 100
    market_avg_vol = volatility.mean() * 100
    print(f"\nMarket Average:")
    print(f"  Average Return:  {market_avg_ret:>+6.2f}%")
    print(f"  Average Volatility: {market_avg_vol:>5.2f}%")

    n_positive = (total_return > 0).sum()
    n_negative = (total_return <= 0).sum()
    print(f"\nBreadth:")
    print(f"  Stocks Up:    {n_positive}")
    print(f"  Stocks Down:  {n_negative}")
    print(f"  {n_positive / (n_positive + n_negative) * 100:>5.1f}% of stocks positive")
    print("=" * 70)
    print()


def run_analysis(tickers=None, sector=None, period="1y", output_dir="charts", generate_charts=True):
    if tickers:
        pass
    elif sector:
        if sector not in SECTORS:
            return None, f"Unknown sector: {sector}"
        tickers = SECTORS[sector]
    else:
        tickers = DEFAULT_TICKERS

    os.makedirs(output_dir, exist_ok=True)

    data = fetch_data(tickers, period)
    if data.empty:
        return None, "No data fetched. Check ticker symbols or internet connection."

    prices, returns, total_return, volatility = calc_returns(data)
    total_return = total_return.dropna()
    volatility = volatility.dropna()

    sector_ret, sector_vol, sector_df = sector_analysis(prices)

    charts = {}
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
        """
    )
    parser.add_argument("--period", default="1y",
                        help="Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, max)")
    parser.add_argument("--sector", help=f"Analyze a specific sector: {', '.join(SECTORS.keys())}")
    parser.add_argument("--ticker", help="Analyze a single ticker")
    parser.add_argument("--output", default="charts", help="Output directory for charts")
    parser.add_argument("--all-charts", action="store_true", help="Generate all chart types")
    parser.add_argument("--no-charts", action="store_true", help="Skip chart generation")
    args = parser.parse_args()

    tickers = None
    if args.ticker:
        tickers = [args.ticker.upper()]
    elif args.sector:
        if args.sector not in SECTORS:
            print(f"Unknown sector: {args.sector}", file=sys.stderr)
            sys.exit(1)

    result, error = run_analysis(tickers=tickers, sector=args.sector,
                                  period=args.period, output_dir=args.output,
                                  generate_charts=not args.no_charts)
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
