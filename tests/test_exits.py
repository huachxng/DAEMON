"""Per-position exit rules — hand-computed:
  Hard stop: DR closes at or below 80% of avg cost -> exit, no debate.
    cost 20.00 -> stop level 16.00. Close 16.00 triggers; 16.01 does not.
  Trend break: the UNDERLYING closes below its 200-day SMA -> exit.
  Hard stop outranks trend break when both fire.
  TDEX/no-underlying names: only the hard stop applies.
"""
from src.risk.exits import exit_signal


def test_hard_stop_at_exactly_80_percent_triggers():
    assert exit_signal(cost_per_unit=20.0, dr_close=16.0,
                       u_close=None, u_sma200=None) == "hard_stop"


def test_just_above_stop_does_not_trigger():
    assert exit_signal(20.0, 16.01, None, None) is None


def test_trend_break_when_underlying_below_sma200():
    assert exit_signal(20.0, 19.0, u_close=100.0, u_sma200=101.0) == "trend_break"


def test_no_signal_when_price_healthy_and_trend_intact():
    assert exit_signal(20.0, 19.0, u_close=102.0, u_sma200=101.0) is None


def test_hard_stop_outranks_trend_break():
    assert exit_signal(20.0, 15.0, u_close=100.0, u_sma200=101.0) == "hard_stop"
