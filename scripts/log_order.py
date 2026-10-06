"""Record an order action at the broker (append-only audit trail).

Usage:
  log_order.py placed live BUY TDEX 3800 10.63 [--note "..."]
  log_order.py cancelled live BUY TDEX 3800 10.63 [--note "..."]
(Fills are recorded via log_trade.py, which also logs the 'filled' event.)
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, load_universe, PROJECT_ROOT
from src.datafeed.store import Store


def main():
    p = argparse.ArgumentParser()
    p.add_argument("event", choices=["placed", "cancelled"])
    p.add_argument("book", choices=["real", "live", "paper"])
    p.add_argument("side", choices=["BUY", "SELL"])
    p.add_argument("ticker")
    p.add_argument("qty", type=float)
    p.add_argument("price", type=float)
    p.add_argument("--note", default="")
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d %H:%M"))
    args = p.parse_args()

    ticker = args.ticker if "." in args.ticker else f"{args.ticker}.BK"
    store = Store(PROJECT_ROOT / load_settings()["data"]["db_path"])
    event = "placed_at_broker" if args.event == "placed" else "cancelled"
    store.log_order_event(args.book, ticker, args.side, args.qty, args.price,
                          event, ts=args.date, note=args.note)
    if args.book == "live":
        from src.digest.levels import record_working_order
        record_working_order(store, ticker, args.price, placed=(args.event == "placed"))
    print(f"recorded: {event} {args.book} {args.side} {args.qty:g} {ticker} @ {args.price}")


if __name__ == "__main__":
    main()
