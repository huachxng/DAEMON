"""The LIVE book snapshot must report ITS OWN pending tickets, not the paper book's.

Regression test for the 2026-08-14 report bug where the LIVE section displayed
paper orders because paper_snapshot hardcoded book="paper" for pending reads.
"""
from src.datafeed.store import Store
from src.paperbot.bot import paper_snapshot

SETTINGS = {
    "books": {
        "live": {"start_cash_thb": 200_000, "halt_buys_below_thb": 160_000,
                 "liquidate_below_thb": 155_000, "hard_floor_thb": 150_000},
        "paper": {"start_cash_thb": 200_000, "halt_buys_below_thb": 160_000,
                  "liquidate_below_thb": 155_000, "hard_floor_thb": 150_000},
    }
}


def test_state_kv_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    assert store.get_state("live_targets") is None
    store.set_state("live_targets", '{"TDEX.BK": 0.25}')
    store.set_state("live_targets", '{"TDEX.BK": 0.30}')  # overwrite wins
    assert store.get_state("live_targets") == '{"TDEX.BK": 0.30}'


def test_live_snapshot_shows_live_tickets_not_paper_orders(tmp_path):
    store = Store(tmp_path / "t.db")
    store.upsert_fx([("2026-08-14", 33.18)])
    store.insert_pending_order(book="live", ticker="MSFT01.BK", side="BUY",
                               qty=3700, created_ts="2026-08-14", after_date="2026-08-14")
    store.insert_pending_order(book="paper", ticker="MSFT", side="BUY",
                               qty=1, created_ts="2026-08-14", after_date="2026-08-13")

    live = paper_snapshot(store, SETTINGS, book="live")
    paper = paper_snapshot(store, SETTINGS, book="paper")

    assert [o["ticker"] for o in live["pending"]] == ["MSFT01.BK"]
    assert [o["ticker"] for o in paper["pending"]] == ["MSFT"]
