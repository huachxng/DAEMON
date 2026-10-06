"""Settrade Open API sync — READ-ONLY by construction, tested against fake payloads.

Hand-computed reconciliation case:
  Broker says: MSFT01 3700, PLTR01 3300, TDEX 4700 (new fill!)
  Ledger says: live MSFT01 3700, PLTR01 3300; live TDEX ticket pending
  Expected:  MSFT01 match · PLTR01 match · TDEX +4700 unlogged (ticket -> confirmed fill)
"""
import pytest

from src.datafeed.settrade_sync import (
    normalize_portfolio, reconcile, load_credentials, ReadOnlyEquity,
)


FAKE_PORTFOLIO = [  # shape of settrade_v2 InvestorEquity.get_portfolios()
    {"symbol": "MSFT01", "actualVolume": 3700, "averagePrice": 4.83, "marketPrice": 4.86},
    {"symbol": "PLTR01", "actualVolume": 3300, "averagePrice": 5.37, "marketPrice": 5.40},
    {"symbol": "TDEX", "actualVolume": 4700, "averagePrice": 10.58, "marketPrice": 10.60},
]


def test_normalize_adds_bk_suffix_and_keeps_qty():
    norm = normalize_portfolio(FAKE_PORTFOLIO)
    assert norm["MSFT01.BK"]["qty"] == 3700
    assert norm["TDEX.BK"]["avg_price"] == pytest.approx(10.58)


def test_normalize_unwraps_sdk_dict_response():
    """Real SDK returns the raw JSON body: a dict wrapping the list (2026-08-16 bug)."""
    wrapped = {"portfolioList": FAKE_PORTFOLIO, "totalPortfolio": {"marketValue": 1}}
    norm = normalize_portfolio(wrapped)
    assert set(norm) == {"MSFT01.BK", "PLTR01.BK", "TDEX.BK"}


def test_normalize_tolerates_unknown_wrapper_key_and_empty():
    assert normalize_portfolio({"data": FAKE_PORTFOLIO[:1]}) == normalize_portfolio(FAKE_PORTFOLIO[:1])
    assert normalize_portfolio({"portfolioList": []}) == {}
    assert normalize_portfolio({}) == {}


def test_reconcile_flags_unlogged_fills_and_matches():
    broker = normalize_portfolio(FAKE_PORTFOLIO)
    ledger = {"MSFT01.BK": 3700, "PLTR01.BK": 3300}
    diff = reconcile(broker, ledger)
    assert diff["matched"] == ["MSFT01.BK", "PLTR01.BK"]
    assert diff["unlogged"] == {"TDEX.BK": 4700}
    assert diff["missing_at_broker"] == {}


def test_reconcile_flags_positions_ledger_has_but_broker_lacks():
    broker = normalize_portfolio(FAKE_PORTFOLIO[:2])
    ledger = {"MSFT01.BK": 3700, "PLTR01.BK": 3300, "GHOST.BK": 100}
    diff = reconcile(broker, ledger)
    assert diff["missing_at_broker"] == {"GHOST.BK": 100}


def test_credentials_missing_file_returns_none(tmp_path):
    assert load_credentials(tmp_path / "nope.yaml") is None


def test_credentials_loaded_from_yaml(tmp_path):
    p = tmp_path / "settrade.yaml"
    p.write_text("app_id: A\napp_secret: S\napp_code: C\nbroker_id: SANDBOX\naccount_no: '1234'\n")
    c = load_credentials(p)
    assert c["broker_id"] == "SANDBOX" and c["account_no"] == "1234"


def test_readonly_wrapper_blocks_every_write_method():
    class FakeEquity:
        def get_portfolios(self): return FAKE_PORTFOLIO
        def place_order(self, **kw): raise AssertionError("must never be reached")
        def cancel_order(self, *a): raise AssertionError("must never be reached")
        def change_order(self, **kw): raise AssertionError("must never be reached")

    ro = ReadOnlyEquity(FakeEquity())
    assert ro.get_portfolios() == FAKE_PORTFOLIO
    for name in ("place_order", "cancel_order", "change_order", "cancel_orders"):
        with pytest.raises(PermissionError, match="read-only"):
            getattr(ro, name)()
