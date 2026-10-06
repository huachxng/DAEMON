"""Track record: append-only order events, per-sale realized P&L, equity snapshots.

Hand-computed realized case (same reference as test_ledger):
  BUY 100 @10 fee 20, BUY 100 @12 fee 20, SELL 150 @13 fee 30
  -> single realized event: qty 150, P&L +290 on 2026-08-03.
"""
import pytest

from src.datafeed.store import Store
from src.portfolio.ledger import Trade, realized_history


def test_order_events_are_append_only_and_read_back_in_order(tmp_path):
    store = Store(tmp_path / "t.db")
    store.log_order_event("live", "TDEX.BK", "BUY", 4700, 10.58, "ticket_issued", ts="2026-08-14")
    store.log_order_event("live", "TDEX.BK", "BUY", 3800, 10.63, "placed_at_broker", ts="2026-08-19")
    store.log_order_event("live", "TDEX.BK", "BUY", 800, 10.58, "filled", ts="2026-08-17")
    events = store.read_order_events("live")
    assert [e["event"] for e in events] == ["ticket_issued", "filled", "placed_at_broker"]
    assert events[2]["qty"] == 3800


def test_pending_order_insert_auto_logs_ticket_event(tmp_path):
    store = Store(tmp_path / "t.db")
    store.insert_pending_order(book="live", ticker="MSFT01.BK", side="BUY",
                               qty=3700, created_ts="2026-08-14", after_date="2026-08-14")
    events = store.read_order_events("live")
    assert len(events) == 1 and events[0]["event"] == "ticket_issued"
    # daily cancel+reissue of the same ticket must NOT spam duplicate events
    store.cancel_unfilled("live")
    store.insert_pending_order(book="live", ticker="MSFT01.BK", side="BUY",
                               qty=3700, created_ts="2026-08-15", after_date="2026-08-15")
    assert len(store.read_order_events("live")) == 1


def test_changed_ticket_qty_logs_new_event(tmp_path):
    store = Store(tmp_path / "t.db")
    store.insert_pending_order(book="live", ticker="TDEX.BK", side="BUY",
                               qty=4700, created_ts="2026-08-14", after_date="2026-08-14")
    store.cancel_unfilled("live")
    store.insert_pending_order(book="live", ticker="TDEX.BK", side="BUY",
                               qty=3800, created_ts="2026-08-18", after_date="2026-08-18")
    assert len(store.read_order_events("live")) == 2


def test_realized_history_hand_computed():
    trades = [
        Trade("live", "TEST", "BUY", 100, 10.0, 20.0, "2026-08-01"),
        Trade("live", "TEST", "BUY", 100, 12.0, 20.0, "2026-08-02"),
        Trade("live", "TEST", "SELL", 150, 13.0, 30.0, "2026-08-03"),
    ]
    hist = realized_history(trades)
    assert len(hist) == 1
    assert hist[0]["ticker"] == "TEST" and hist[0]["qty"] == 150
    assert hist[0]["pl"] == pytest.approx(290.0)
    assert hist[0]["ts"] == "2026-08-03"


def test_equity_snapshot_upsert_and_history(tmp_path):
    store = Store(tmp_path / "t.db")
    store.snapshot_equity("2026-08-20", "live", 200195.0)
    store.snapshot_equity("2026-08-20", "live", 200200.0)   # same-day rerun wins
    store.snapshot_equity("2026-08-21", "live", 201000.0)
    hist = store.read_equity_history("live")
    assert [h["equity"] for h in hist] == [200200.0, 201000.0]
