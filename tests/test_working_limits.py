"""Working-order limits live in DB state (hub-updatable), not in code."""
import json

from src.datafeed.store import Store
from src.digest.levels import working_limits


def test_state_overrides_and_extends_defaults(tmp_path):
    store = Store(tmp_path / "t.db")
    assert working_limits(store, defaults={"TDEX.BK": 10.63}) == {"TDEX.BK": 10.63}
    store.set_state("working_limits", json.dumps({"AMZN06.BK": 2.18}))
    assert working_limits(store, defaults={"TDEX.BK": 10.63}) == {"AMZN06.BK": 2.18}


def test_log_order_updates_working_limits(tmp_path):
    from src.digest.levels import record_working_order
    store = Store(tmp_path / "t.db")
    record_working_order(store, "AMZN06.BK", 2.18, placed=True)
    record_working_order(store, "MSFT01.BK", 4.62, placed=True)
    record_working_order(store, "AMZN06.BK", None, placed=False)   # cancelled/filled
    assert working_limits(store, defaults={}) == {"MSFT01.BK": 4.62}
