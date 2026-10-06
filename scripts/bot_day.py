"""Run the paper bot's daily cycle: fill pending orders, decide, queue new ones.

Usage:  .venv/bin/python scripts/bot_day.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, PROJECT_ROOT
from src.datafeed.store import Store
from src.paperbot.bot import run_day


def main():
    settings = load_settings()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    result = run_day(store, settings)
    snap = result["snapshot"]
    print(f"filled {result['filled']} orders, queued {result['queued']} new")
    print(f"equity ฿{snap['equity']:,.0f} (cash ฿{snap['cash']:,.0f} + "
          f"positions ฿{snap['value']:,.0f}) · breaker: {snap['state']}")
    for o in snap["pending"]:
        print(f"  pending: {o['side']} {o['qty']:g} {o['ticker']}")


if __name__ == "__main__":
    main()
