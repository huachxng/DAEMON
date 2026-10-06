"""Print radar trigger lines for held live positions; silent when quiet.

Usage:  .venv/bin/python scripts/radar.py
The morning cron may do web research ONLY when this prints something.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from src.config import load_settings, load_universe, PROJECT_ROOT
from src.datafeed.store import Store
from src.paperbot.bot import paper_snapshot
from src.risk.radar import move_trigger, earnings_trigger


def main():
    settings, uni = load_settings(), load_universe()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    snap = paper_snapshot(store, settings, book="live")
    held = {r["ticker"] for r in snap["rows"]}
    u_of = {p["dr"]: p["underlying"] for p in uni["dr_map"]}
    earnings = yaml.safe_load(open(PROJECT_ROOT / "config" / "earnings.yaml")) or {}
    today = date.today().isoformat()

    for dr in sorted(held):
        u = u_of.get(dr)
        if not u:
            continue
        df = store.read_prices(u)
        closes = df["close"].dropna()
        if len(closes) >= 2:
            t = move_trigger(u, float(closes.iloc[-2]), float(closes.iloc[-1]))
            if t:
                print(f"RADAR: {t} (held via {dr.replace('.BK', '')})")
        if u in earnings:
            t = earnings_trigger(u, str(earnings[u]), today)
            if t:
                print(f"RADAR: {t} (held via {dr.replace('.BK', '')})")


if __name__ == "__main__":
    main()
