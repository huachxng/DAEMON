"""SET price tick sizes. Stops round DOWN so the trigger is always a valid,
slightly-safer price the exchange will accept."""
import math

BANDS = [  # (upper_bound_exclusive, tick)
    (2, 0.01), (5, 0.02), (10, 0.05), (25, 0.10), (100, 0.25),
    (200, 0.50), (400, 1.00), (float("inf"), 2.00),
]


def set_tick(price: float) -> float:
    for bound, tick in BANDS:
        if price < bound:
            return tick
    raise AssertionError("unreachable")


def round_down_to_tick(price: float) -> float:
    tick = set_tick(price)
    return math.floor(price / tick + 1e-9) * tick
