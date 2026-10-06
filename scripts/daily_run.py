"""The daemon's scheduled cycle: update data -> bot -> alerts -> report.

Usage:  .venv/bin/python scripts/daily_run.py
Prints a compact bilingual digest; lines starting with URGENT: are meant to be
push-notified by whoever runs this (the scheduled agent).
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, PROJECT_ROOT
from src.datafeed.store import Store
from src.datafeed.fetch import update_all
from src.paperbot.bot import run_day
from src.alerts.engine import evaluate
from src.digest.report import build_report


def main():
    settings = load_settings()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])

    results = update_all(store)
    problems = [f"{s}: {r}" for s, r in results.items() if "ERROR" in r or r == "NO DATA"]

    bot = run_day(store, settings)
    snap = bot["snapshot"]

    alerts = evaluate(store, settings)

    # Daily options-chain snapshot (builds our own IV-rank history over time).
    import subprocess
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "snapshot_options.py")],
                   capture_output=True, timeout=600)

    for book_name, book_snap in (("live", bot["live"]), ("paper", snap)):
        store.snapshot_equity(date.today().isoformat(), book_name, book_snap["equity"])

    out = PROJECT_ROOT / "reports" / f"portfolio_{date.today().isoformat()}.html"

    out.parent.mkdir(exist_ok=True)
    out.write_text(build_report(store, settings), encoding="utf-8")
    print(f"DIGEST {date.today().isoformat()}")
    live = bot["live"]
    print(f"live: equity ฿{live['equity']:,.0f} · breaker {live['state']}")
    if bot["tickets"]:
        print("URGENT: new LIVE order tickets await your execution in Streaming:")
        for o in bot["tickets"]:
            print(f"  TICKET: {o.side} {o.qty:g} {o.ticker.replace('.BK','')} (limit ~ last close)")
    elif live["pending"]:
        print("reminder — unexecuted LIVE tickets:")
        for o in live["pending"]:
            print(f"  TICKET: {o['side']} {o['qty']:g} {o['ticker'].replace('.BK','')}")
    print(f"paper: equity ฿{snap['equity']:,.0f} · breaker {snap['state']} · "
          f"filled {bot['filled']} · queued {bot['queued']}")
    for o in snap["pending"]:
        print(f"  pending: {o['side']} {o['qty']:g} {o['ticker']}")
    for a in alerts:
        prefix = "URGENT: " if a.severity == "urgent" else "info: "
        print(f"{prefix}{a.msg_en}")
        print(f"{prefix}{a.msg_th}")
    if problems:
        print(f"data problems: {'; '.join(problems)}")
    print(f"report: {out}")


if __name__ == "__main__":
    main()
