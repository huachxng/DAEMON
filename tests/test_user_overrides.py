"""User overrides: the user may decline a ROTATION sell ("hold MSFT01"), and the
daemon must stop re-ticketing it daily. Protective exits (hard stop, trend
break) and breaker liquidation are NOT overridable — they guard the floor."""
from src.paperbot.sizing import Order, apply_user_overrides


def test_hold_override_drops_rotation_sell_only():
    orders = [Order("MSFT01.BK", "SELL", 3700), Order("ASML01.BK", "SELL", 300),
              Order("PLTR01.BK", "BUY", 3600)]
    kept = apply_user_overrides(orders, overrides={"MSFT01.BK": "hold"}, protected=set())
    assert [(o.side, o.ticker) for o in kept] == [("SELL", "ASML01.BK"), ("BUY", "PLTR01.BK")]


def test_protective_exit_beats_hold_override():
    orders = [Order("MSFT01.BK", "SELL", 3700)]
    kept = apply_user_overrides(orders, overrides={"MSFT01.BK": "hold"},
                                protected={"MSFT01.BK"})
    assert len(kept) == 1
