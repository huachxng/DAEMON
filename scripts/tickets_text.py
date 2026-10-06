"""Plain-text order block for the command-hub email. Concise, copy-paste ready.

Usage:  .venv/bin/python scripts/tickets_text.py
Prints: open tickets (with limit = last close, rounded to tick), est. cost,
        standing cut-loss levels, and how to report back.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, PROJECT_ROOT
from src.datafeed.store import Store
from src.digest.levels import levels_rows
from src.paperbot.bot import paper_snapshot, _price_thb
from src.portfolio.ticks import round_down_to_tick


def main():
    settings = load_settings()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    snap = paper_snapshot(store, settings, book="live")
    lines = [f"CLAUDE TRADE — orders for {date.today().isoformat()}",
             f"Live sleeve ฿{snap['equity']:,.0f} · breaker {snap['state']}", ""]
    if snap["pending"]:
        lines.append("ORDERS (limit = last close; use Streaming limit orders):")
        total = 0.0
        for o in snap["pending"]:
            _, px = _price_thb(store, o["ticker"], "close", snap["fx"])
            lim = round_down_to_tick(px) if px else 0
            est = o["qty"] * lim
            total += est
            lines.append(f"  {o['side']} {o['qty']:,.0f} {o['ticker'].replace('.BK','')} @ limit {lim:.2f}   (~฿{est:,.0f})")
        lines += [f"  total ~฿{total:,.0f}", ""]
    else:
        lines += ["ORDERS: none today — nothing to do.", ""]
    lines.append("STANDING CUT-LOSS (Cond. SELL triggers, keep these in Streaming):")
    for r in levels_rows(store, settings):
        lines.append(f"  {r['ticker']:9s} {r['qty']:>6,.0f}  cut-loss {r['stop']:.2f}")
    lines += ["", "REPORT BACK by replying to this email, one line per fill, e.g.:",
              "  filled 900 MSFT01 @ 4.80", "  placed 2000 AMZN06 @ 2.18 (waiting)",
              "  cancelled 100 ASML01", "A screenshot works too. Partial fills: give the matched qty."]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
