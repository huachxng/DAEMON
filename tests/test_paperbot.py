"""Circuit breaker + order sizing — the code that guards the ฿150k floor.

Breaker thresholds from settings: halt buys below 160k, liquidate below 155k.
Sizing hand-case:
  equity 200,000; targets TDEX 45% (lot 100), AAPL 9%;
  TDEX @ 10.64 -> raw 90,000/10.64 = 8458.6 -> floor to lot 100 -> 8400 units
  AAPL @ 10,000 THB/share -> 18,000/10,000 = 1.8 -> 1 share
  Already held: 0 -> two BUY orders with those quantities.
"""
import pytest

from src.paperbot.breaker import breaker_state
from src.paperbot.sizing import orders_from_targets


SETTINGS = {"books": {"paper": {
    "start_cash_thb": 200_000, "halt_buys_below_thb": 160_000,
    "liquidate_below_thb": 155_000, "hard_floor_thb": 150_000,
    "max_position_pct": 15, "min_cash_buffer_pct": 10,
}}}


def test_breaker_normal_above_halt_line():
    assert breaker_state(200_000, SETTINGS) == "normal"
    assert breaker_state(160_000.01, SETTINGS) == "normal"


def test_breaker_halts_buys_between_lines():
    assert breaker_state(160_000, SETTINGS) == "halt_buys"
    assert breaker_state(155_000.01, SETTINGS) == "halt_buys"


def test_breaker_liquidates_at_or_below_line():
    assert breaker_state(155_000, SETTINGS) == "liquidate"
    assert breaker_state(150_001, SETTINGS) == "liquidate"


def test_equity_path_toward_floor_always_liquidates_before_150k():
    # Any equity above the hard floor must already be in a defensive state
    # before it could reach 150k: there is no equity in (150k, 155k] that
    # is not 'liquidate', and none in (155k, 160k] that is not 'halt_buys'.
    for equity in range(150_001, 155_001, 50):
        assert breaker_state(float(equity), SETTINGS) == "liquidate"
    for equity in range(155_001, 160_001, 50):
        assert breaker_state(float(equity), SETTINGS) == "halt_buys"


def test_sizing_hand_case_with_lot_rounding():
    orders = orders_from_targets(
        equity=200_000,
        targets={"TDEX.BK": 0.45, "AAPL": 0.09},
        held={},
        prices_thb={"TDEX.BK": 10.64, "AAPL": 10_000.0},
        lot_sizes={"TDEX.BK": 100},
    )
    by_ticker = {o.ticker: o for o in orders}
    assert (by_ticker["TDEX.BK"].side, by_ticker["TDEX.BK"].qty) == ("BUY", 8400)
    assert (by_ticker["AAPL"].side, by_ticker["AAPL"].qty) == ("BUY", 1)


def test_sizing_emits_sell_when_overweight():
    orders = orders_from_targets(
        equity=200_000,
        targets={"AAPL": 0.0},
        held={"AAPL": 5},
        prices_thb={"AAPL": 10_000.0},
        lot_sizes={},
    )
    assert [(o.side, o.qty, o.ticker) for o in orders] == [("SELL", 5, "AAPL")]


def test_affordable_picks_substitute_down_the_ranking():
    from src.paperbot.sizing import pick_affordable
    ranking = ["ASML", "MU", "AMZN", "AMD", "UNH", "NVDA", "TSLA"]
    prices = {"ASML": 61_000, "MU": 31_500, "AMZN": 8_800, "AMD": 16_000,
              "UNH": 13_200, "NVDA": 7_500, "TSLA": 11_300}
    # slot ฿18,000: ASML and MU are unaffordable -> next in line take their places
    assert pick_affordable(ranking, prices, slot_thb=18_000, n=5) == \
        ["AMZN", "AMD", "UNH", "NVDA", "TSLA"]


def test_affordable_picks_returns_fewer_when_universe_runs_dry():
    from src.paperbot.sizing import pick_affordable
    assert pick_affordable(["A", "B"], {"A": 50_000, "B": 9_000}, 18_000, n=5) == ["B"]


def test_sizing_skips_dust_drift():
    # 1 share of a 10k stock held, target implies 1.08 shares -> drift < 1 share -> no order
    orders = orders_from_targets(
        equity=120_000, targets={"AAPL": 0.09}, held={"AAPL": 1},
        prices_thb={"AAPL": 10_000.0}, lot_sizes={},
    )
    assert orders == []
