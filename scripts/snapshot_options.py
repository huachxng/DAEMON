"""Snapshot US option chains (near-ATM, nearest 2 expiries) into the store.

Run daily; each snapshot is one more day of our own IV history. IV *rank*
becomes meaningful once weeks of these accumulate — until then the report
uses the realized-vol percentile as an honest proxy.

Usage:  .venv/bin/python scripts/snapshot_options.py
"""
import sys
from datetime import date
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, PROJECT_ROOT
from src.datafeed.store import Store
from src.portfolio.ledger import build_positions


def tickers_to_snapshot(store) -> list:
    held = [t for t, p in build_positions(store.read_trades("paper")).items()
            if p.qty > 0 and not t.endswith(".BK")]
    queued = [o["ticker"] for o in store.unfilled_orders("paper")
              if not o["ticker"].endswith(".BK")]
    return sorted(set(held) | set(queued))


def main():
    settings = load_settings()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    today = date.today().isoformat()
    total = 0
    for t in tickers_to_snapshot(store):
        try:
            tkr = yf.Ticker(t)
            spot = float(tkr.fast_info["last_price"])
            for expiry in tkr.options[:2]:
                chain = tkr.option_chain(expiry)
                rows = []
                import pandas as pd

                def num(v, cast=float):
                    return cast(0 if pd.isna(v) else v)  # NaN is truthy; guard explicitly

                for kind, df in (("C", chain.calls), ("P", chain.puts)):
                    near = df[(df["strike"] > spot * 0.8) & (df["strike"] < spot * 1.2)]
                    for _, r in near.iterrows():
                        rows.append((t, today, expiry, float(r["strike"]), kind,
                                     num(r["bid"]), num(r["ask"]),
                                     num(r["impliedVolatility"]),
                                     num(r["openInterest"], int)))
                store.conn.executemany(
                    "INSERT OR REPLACE INTO options_snapshots "
                    "(ticker, date, expiry, strike, type, bid, ask, iv, oi) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
                store.conn.commit()
                total += len(rows)
        except Exception as e:
            print(f"  {t}: snapshot failed ({type(e).__name__}: {e})")
    print(f"snapshotted {total} contracts on {today}")


if __name__ == "__main__":
    main()
