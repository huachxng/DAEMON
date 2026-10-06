"""A NaN price must never crash sizing or produce an order (NaN is truthy!)."""
import math

from src.paperbot.sizing import orders_from_targets


def test_nan_price_is_skipped_not_crashed():
    orders = orders_from_targets(
        equity=200_000,
        targets={"GOOD.BK": 0.25, "BAD.BK": 0.25},
        held={},
        prices_thb={"GOOD.BK": 10.0, "BAD.BK": float("nan")},
        lot_sizes={"GOOD.BK": 100, "BAD.BK": 100},
    )
    assert [o.ticker for o in orders] == ["GOOD.BK"]
