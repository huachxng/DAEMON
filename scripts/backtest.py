"""Backtest the launch strategies on stored history and write a results note.

Usage:  .venv/bin/python scripts/backtest.py
Output: docs/backtests/<date>.md + summary on stdout.

Honesty notes baked into the output:
- Benchmark = buy-and-hold of TDEX.BK (SET50) / ^GSPC on ADJUSTED closes
  (dividends reinvested), which is the harder-to-beat comparison.
- Strategy trades on RAW opens/closes (you can't buy the adjusted price).
- Universe = today's watchlist -> survivorship bias is present and documented.
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, load_universe, PROJECT_ROOT
from src.datafeed.store import Store
from src.backtest.engine import run_backtest
from src.backtest.momentum import TopNMomentum
from src.portfolio.fees import thai_fee, us_paper_fee


def load_prices(store, tickers):
    out = {}
    for t in tickers:
        df = store.read_prices(t)
        if df.empty:
            continue
        frame = pd.DataFrame(
            {"open": df["open"].values, "close": df["close"].values},
            index=pd.to_datetime(df["date"]),
        )
        frame["close"] = frame["close"].ffill()
        out[t] = frame
    return out


def bench_return(store, ticker, start, end):
    df = store.read_prices(ticker)
    s = pd.Series(df["adj_close"].values, index=pd.to_datetime(df["date"]))
    s = s[(s.index >= start) & (s.index <= end)]
    return 100 * (s.iloc[-1] / s.iloc[0] - 1)


def run_suite(name, prices, cash, fee_fn, settings):
    strat = lambda: TopNMomentum(n=5, lookback=126, sma_filter=200)
    with_fees = run_backtest(prices, strat(), cash, fee_fn, slippage_bps=10)
    no_fees = run_backtest(prices, strat(), cash, lambda n, q: 0.0, slippage_bps=0)
    return name, with_fees, no_fees


def main():
    settings = load_settings()
    uni = load_universe()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])

    set_prices = load_prices(store, [f"{t}.BK" for t in uni["watchlist"]["set"]])
    us_prices = load_prices(store, uni["watchlist"]["us"])

    suites = [
        run_suite("SET momentum (THB)", set_prices, 200_000,
                  lambda notional, qty: thai_fee(notional, settings), settings),
        run_suite("US momentum (USD)", us_prices, 6_000,
                  lambda notional, qty: us_paper_fee(qty, settings), settings),
    ]

    lines = [f"# Backtest results — {date.today().isoformat()}", ""]
    for name, wf, nf in suites:
        start, end = wf.equity.index[0], wf.equity.index[-1]
        bench_ticker = uni["benchmarks"]["set_fallback"] if "SET" in name else uni["benchmarks"]["us"]
        bench = bench_return(store, bench_ticker, start, end)
        lines += [
            f"## {name}",
            f"- Window: {start.date()} → {end.date()}  (top-5 of 20, 126d momentum, 200d SMA filter, monthly)",
            f"- **With fees+slippage:** total {wf.stats['total_return_pct']}% · CAGR {wf.stats['cagr_pct']}% · "
            f"maxDD {wf.stats['max_dd_pct']}% · Sharpe {wf.stats['sharpe']} · {wf.stats['n_trades']} trades · "
            f"fees {wf.stats['fees_paid']:,.0f}",
            f"- Without fees: total {nf.stats['total_return_pct']}% (fee drag = "
            f"{nf.stats['total_return_pct'] - wf.stats['total_return_pct']:.1f} pp)",
            f"- Buy-and-hold {bench_ticker} same window (adj, divs reinvested): {bench:.1f}%",
            "",
        ]
    out_dir = PROJECT_ROOT / "docs" / "backtests"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{date.today().isoformat()}.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"written: {out}")


if __name__ == "__main__":
    main()
