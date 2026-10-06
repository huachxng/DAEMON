"""Read-only sync with the real Bualuang account via Settrade Open API.

Usage:  .venv/bin/python scripts/settrade_sync.py            # reconcile + report
        .venv/bin/python scripts/settrade_sync.py --apply    # also log unlogged
                                                             #   fills as LIVE-book
                                                             #   trades at broker avg
Never places, changes, or cancels an order (see src/datafeed/settrade_sync.py).
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, PROJECT_ROOT
from src.datafeed.store import Store
from src.datafeed.settrade_sync import (
    load_credentials, connect, normalize_portfolio, reconcile,
)
from src.portfolio.fees import thai_fee
from src.portfolio.ledger import build_positions


def main():
    creds = load_credentials()
    if creds is None:
        print("no config/settrade.yaml — copy config/settrade.example.yaml, fill it in "
              "yourself (Claude never handles the values), then rerun.")
        return 2
    settings = load_settings()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])

    eq = connect(creds)
    info = eq.get_account_info()
    broker = normalize_portfolio(eq.get_portfolios())

    ledger_qty = {}
    for book in ("real", "live"):
        for t, p in build_positions(store.read_trades(book)).items():
            if p.qty > 0:
                ledger_qty[t] = ledger_qty.get(t, 0) + p.qty
    diff = reconcile(broker, ledger_qty)

    env = "SANDBOX (paper)" if creds["broker_id"].upper() == "SANDBOX" else "PRODUCTION"
    print(f"Settrade {env} · account {creds['account_no']}")
    cash = None
    for k in ("cashBalance", "cash_balance", "lineAvailable", "excessEquity"):
        if isinstance(info, dict) and info.get(k) is not None:
            cash = f"{k}={info[k]}"
            break
    print(f"account info: {cash or ('keys=' + ', '.join(list(info)[:8]) if isinstance(info, dict) else info)}")
    print(f"matched: {', '.join(t.replace('.BK','') for t in diff['matched']) or '—'}")
    for t, q in diff["unlogged"].items():
        print(f"UNLOGGED at broker: {t.replace('.BK','')} +{q:g} "
              f"(broker avg {broker[t]['avg_price']:.2f})")
    for t, q in diff["missing_at_broker"].items():
        print(f"LEDGER-ONLY: {t.replace('.BK','')} {q:g} not at broker — investigate")

    if "--apply" in sys.argv and diff["unlogged"]:
        pending = {o["ticker"] for o in store.unfilled_orders("live")}
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for t, q in diff["unlogged"].items():
            if t not in pending:
                print(f"skip {t}: no live ticket for it — log manually if it's the daemon's")
                continue
            px = broker[t]["avg_price"]
            store.insert_trade(book="live", ticker=t, side="BUY", qty=q, price=px,
                               fees=round(thai_fee(q * px, settings), 2), ts=now,
                               note="auto-logged from Settrade sync (broker avg price)")
            print(f"logged LIVE BUY {q:g} {t.replace('.BK','')} @ {px:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
