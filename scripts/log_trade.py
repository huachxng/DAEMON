"""Log a real (or paper) trade into the book.

Usage:
  .venv/bin/python scripts/log_trade.py BOOK SIDE TICKER QTY PRICE
      [--fees F] [--date YYYY-MM-DD] [--note "..."]

Examples:
  log_trade.py live BUY MSFT01 1000 4.80 --date 2026-06-01
  log_trade.py live SELL TDEX 100 10.60 --date 2026-08-01

Fees: if --fees is omitted and the ticker is Thai (.BK), the BLS commission
model from settings.yaml is applied automatically.
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, load_universe, all_yahoo_symbols, PROJECT_ROOT
from src.datafeed.store import Store
from src.portfolio.fees import thai_fee


def resolve_ticker(name: str) -> str:
    """Accept 'META01' or 'META01.BK' or 'AAPL' — return the Yahoo symbol."""
    symbols = all_yahoo_symbols(load_universe())
    if name in symbols:
        return name
    if f"{name}.BK" in symbols:
        return f"{name}.BK"
    return name  # allow off-universe tickers, they just won't have prices yet


def main():
    p = argparse.ArgumentParser()
    p.add_argument("book", choices=["real", "live", "paper"])
    p.add_argument("side", choices=["BUY", "SELL"])
    p.add_argument("ticker")
    p.add_argument("qty", type=float)
    p.add_argument("price", type=float)
    p.add_argument("--fees", type=float, default=None)
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--note", default="")
    args = p.parse_args()

    settings = load_settings()
    ticker = resolve_ticker(args.ticker)
    fees = args.fees
    if fees is None:
        fees = thai_fee(args.qty * args.price, settings) if ticker.endswith(".BK") else 0.0

    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    store.insert_trade(book=args.book, ticker=ticker, side=args.side,
                       qty=args.qty, price=args.price, fees=round(fees, 2),
                       ts=args.date, note=args.note)
    print(f"logged: {args.book} {args.side} {args.qty:g} {ticker} @ {args.price} "
          f"fees {fees:.2f} on {args.date}")


if __name__ == "__main__":
    main()
