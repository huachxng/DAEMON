"""Pull the latest EOD data for the whole universe.

Usage:  .venv/bin/python scripts/update.py [--deep]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, PROJECT_ROOT
from src.datafeed.store import Store
from src.datafeed.fetch import update_all


def main():
    deep = "--deep" in sys.argv
    settings = load_settings()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    results = update_all(store, deep=deep)
    problems = {s: r for s, r in results.items() if "ERROR" in r or r == "NO DATA"}
    ok = len(results) - len(problems)
    print(f"updated {ok}/{len(results)} symbols")
    for sym, r in problems.items():
        print(f"  PROBLEM {sym}: {r}")


if __name__ == "__main__":
    main()
