"""Trades and FX roundtrip through the store, coming back as ledger objects."""
import pytest

from src.datafeed.store import Store
from src.portfolio.ledger import build_positions


def test_trades_roundtrip_and_feed_the_ledger(tmp_path):
    store = Store(tmp_path / "t.db")
    store.insert_trade(book="real", ticker="META01.BK", side="BUY",
                       qty=1000, price=5.50, fees=8.64, ts="2026-06-01", note="entry")
    store.insert_trade(book="real", ticker="META01.BK", side="BUY",
                       qty=500, price=6.00, fees=4.71, ts="2026-07-01")
    store.insert_trade(book="paper", ticker="AAPL", side="BUY",
                       qty=10, price=300.0, fees=1.0, ts="2026-08-01")

    real_trades = store.read_trades(book="real")
    assert len(real_trades) == 2
    pos = build_positions(real_trades)["META01.BK"]
    assert pos.qty == 1500
    assert pos.cost_basis == pytest.approx(1000 * 5.50 + 8.64 + 500 * 6.00 + 4.71)

    assert len(store.read_trades(book="paper")) == 1


def test_dividends_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.upsert_dividends("META01.BK", [("2026-06-15", "2026-07-01", 0.05)])
    store.upsert_dividends("META01.BK", [("2026-06-15", "2026-07-01", 0.06)])  # correction
    divs = store.read_dividends("META01.BK")
    assert len(divs) == 1
    assert divs[0]["amount"] == 0.06
    assert divs[0]["wht"] == 0.10  # Thai default withholding


def test_fx_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.upsert_fx([("2026-08-12", 33.10), ("2026-08-13", 33.18)])
    store.upsert_fx([("2026-08-13", 33.20)])  # correction wins
    fx = store.read_fx()
    assert fx["2026-08-13"] == 33.20
    assert store.latest_fx() == 33.20
