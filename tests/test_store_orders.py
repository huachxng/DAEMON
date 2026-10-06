"""Pending orders + journal roundtrip."""
from src.datafeed.store import Store


def test_pending_order_lifecycle(tmp_path):
    store = Store(tmp_path / "t.db")
    store.insert_pending_order(book="paper", ticker="TDEX.BK", side="BUY",
                               qty=8400, created_ts="2026-08-14",
                               after_date="2026-08-14")
    unfilled = store.unfilled_orders("paper")
    assert len(unfilled) == 1
    order = unfilled[0]
    assert (order["ticker"], order["side"], order["qty"]) == ("TDEX.BK", "BUY", 8400)
    # The fill gate: only a bar strictly newer than after_date may fill this.
    assert order["after_date"] == "2026-08-14"

    store.mark_order_filled(order["id"])
    assert store.unfilled_orders("paper") == []


def test_cancel_unfilled_clears_queue(tmp_path):
    store = Store(tmp_path / "t.db")
    store.insert_pending_order("paper", "AAPL", "BUY", 1, "2026-08-14", "2026-08-13")
    store.insert_pending_order("paper", "TDEX.BK", "BUY", 100, "2026-08-14", "2026-08-14")
    store.cancel_unfilled("paper")
    assert store.unfilled_orders("paper") == []


def test_journal_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.insert_journal(ts="2026-08-14", book="paper", action="BUY 8400 TDEX.BK",
                         reasoning="Thai sleeve null strategy: 45% target", rule_id="thai-null")
    store.insert_journal(ts="2026-08-14", book="paper", action="no-op",
                         reasoning="US sleeve waits for month boundary", rule_id="us-momentum")
    tail = store.read_journal_tail(limit=5)
    assert len(tail) == 2
    assert tail[0]["action"] == "no-op"  # newest first
