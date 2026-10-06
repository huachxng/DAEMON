"""Two live-sleeve bugs found 2026-08-22.

Dust: the daemon issued SELL 100 AMZN06 (฿212) as a drift trim. Trims below
the min ticket notional must be dropped on BOTH sides; only full exits
(target weight 0) and liquidations may be small.

Re-pick cadence: the quarter counter lived on a per-run object, so the sleeve
would re-pick on the first trading day of EVERY month. Quarterly means
>= 3 calendar months since the last pick: picked 2026-08-14 -> due 2026-11-02,
not 2026-09-01 or 2026-10-01.
"""
from src.paperbot.sizing import Order, drop_dust
from src.backtest.momentum import is_repick_due


def test_drop_dust_removes_small_trims_on_both_sides():
    orders = [Order("AMZN06.BK", "SELL", 100), Order("TDEX.BK", "BUY", 100),
              Order("PLTR01.BK", "BUY", 3300)]
    prices = {"AMZN06.BK": 2.12, "TDEX.BK": 10.6, "PLTR01.BK": 5.4}
    targets = {"AMZN06.BK": 0.09, "TDEX.BK": 0.25, "PLTR01.BK": 0.09}
    kept = drop_dust(orders, prices, targets, min_notional=5000)
    assert [(o.side, o.ticker) for o in kept] == [("BUY", "PLTR01.BK")]


def test_drop_dust_keeps_full_exit_even_if_small():
    orders = [Order("AMZN06.BK", "SELL", 100)]
    kept = drop_dust(orders, {"AMZN06.BK": 2.12}, {"AMZN06.BK": 0.0}, 5000)
    assert len(kept) == 1


def test_repick_due_only_after_three_months():
    assert not is_repick_due("2026-08-14", "2026-09-01", every_months=3)
    assert not is_repick_due("2026-08-14", "2026-10-01", every_months=3)
    assert is_repick_due("2026-08-14", "2026-11-02", every_months=3)
    assert is_repick_due(None, "2026-09-01", every_months=3)   # never picked -> due
