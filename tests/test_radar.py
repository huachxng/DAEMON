"""News/event radar triggers — hand-computed:
  Move: underlying closed 3.2% down -> trigger; 2.9% -> silent. Threshold 3%.
  Earnings: within 5 TRADING days -> trigger. MU reports Tue 2026-09-23:
    on Tue 2026-09-16 that is 5 trading days (17,18,21,22,23) -> trigger;
    on Mon 2026-09-14 it is 7 -> silent; on 2026-09-24 (past) -> silent.
"""
from src.risk.radar import move_trigger, earnings_trigger, trading_days_until


def test_move_trigger_band():
    assert move_trigger("MU", prev_close=100.0, close=96.8) is not None   # -3.2%
    assert move_trigger("MU", prev_close=100.0, close=103.2) is not None  # +3.2%
    assert move_trigger("MU", prev_close=100.0, close=97.1) is None       # -2.9%


def test_trading_days_until_skips_weekends():
    assert trading_days_until("2026-09-16", "2026-09-23") == 5
    assert trading_days_until("2026-09-14", "2026-09-23") == 7
    assert trading_days_until("2026-09-23", "2026-09-23") == 0


def test_earnings_trigger_window():
    assert earnings_trigger("MU", "2026-09-23", today="2026-09-16") is not None
    assert earnings_trigger("MU", "2026-09-23", today="2026-09-14") is None
    assert earnings_trigger("MU", "2026-09-23", today="2026-09-24") is None
