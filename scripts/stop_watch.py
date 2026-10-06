"""Check delayed quotes against cut-loss levels; print PUSH lines only when
something is new. Designed for a cheap 2-hourly cron: silent output = no push.

Usage:  .venv/bin/python scripts/stop_watch.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yfinance as yf

from src.config import load_settings, PROJECT_ROOT
from src.datafeed.store import Store
from src.digest.levels import levels_rows
from src.risk.stop_watch import proximity, should_notify


def last_price(ticker_bk: str):
    try:
        fi = yf.Ticker(ticker_bk).fast_info
        px = fi.get("lastPrice") or fi.get("last_price")
        return float(px) if px else None
    except Exception:
        return None


def main():
    settings = load_settings()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    sent = json.loads(store.get_state("stop_watch_sent") or "{}")
    today = datetime.now().strftime("%Y-%m-%d")

    seen = set()
    for r in levels_rows(store, settings):
        t = r["ticker"]
        if r.get("status") == "WORKING" or t in seen:
            continue   # only held positions; first row per ticker (held before working)
        seen.add(t)
        bk = t if t.endswith(".BK") else f"{t}.BK"
        last = last_price(bk)
        if last is None:
            continue
        level = proximity(last, r["stop"])
        if level and should_notify(sent, t, level, today):
            gap = 100 * (last / r["stop"] - 1)
            if level == "breach":
                print(f"PUSH: 🔴 CUT-LOSS BREACHED {t}: last {last:.2f} ≤ stop {r['stop']:.2f} "
                      f"— SELL {r['qty']:,.0f} now if you agree; daemon issues the ticket at the "
                      f"next run / ราคาหลุดจุดตัดขาดทุนแล้ว")
            else:
                print(f"PUSH: 🟠 NEAR CUT-LOSS {t}: last {last:.2f}, stop {r['stop']:.2f} "
                      f"({gap:+.1f}%) — no broker order is protecting this; watch it / "
                      f"ใกล้จุดตัดขาดทุน ยังไม่มีคำสั่งขายรออยู่ที่โบรกเกอร์")
    store.set_state("stop_watch_sent", json.dumps(sent))


if __name__ == "__main__":
    main()
