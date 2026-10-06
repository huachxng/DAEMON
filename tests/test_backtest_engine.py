"""Backtest engine — hand-computed round trip.

Prices for ticker A (open / close):
  d1: 10 / 10     d2: 10 / 11     d3: 12 / 12     d4: 13 / 13

Strategy: all-in on d1's close -> filled at d2 OPEN (never same-day close!).
Flat fee 10, zero slippage, cash 1000:
  d2 fill @10:  qty = floor((1000-10)/10) = 99 -> cost 990 + fee 10 -> cash 0
  equity: d1 = 1000, d2 = 99*11 = 1089, d3 = 99*12 = 1188
Exit signal on d3's close -> filled at d4 OPEN @13:
  proceeds = 99*13 - 10 = 1277 -> equity d4 = 1277 (all cash)
"""
import pandas as pd
import pytest

from src.backtest.engine import run_backtest


def make_prices():
    dates = pd.date_range("2026-01-05", periods=4, freq="B")
    return {
        "A": pd.DataFrame(
            {"open": [10.0, 10.0, 12.0, 13.0], "close": [10.0, 11.0, 12.0, 13.0]},
            index=dates,
        )
    }


class AllInThenOut:
    """Enter on the first day, exit on the third."""
    def target_weights(self, closes):
        if len(closes) == 1:
            return {"A": 1.0}
        if len(closes) == 3:
            return {"A": 0.0}
        return None


def flat_fee(notional, qty):
    return 10.0


def test_round_trip_equity_matches_hand_computation():
    result = run_backtest(make_prices(), AllInThenOut(), initial_cash=1000,
                          fee_fn=flat_fee, slippage_bps=0)
    assert list(result.equity.round(2)) == [1000.0, 1089.0, 1188.0, 1277.0]
    assert len(result.trades) == 2
    buy, sell = result.trades
    assert (buy.side, buy.qty, buy.fill_price) == ("BUY", 99, 10.0)
    assert (sell.side, sell.qty, sell.fill_price) == ("SELL", 99, 13.0)
    assert result.fees_paid == pytest.approx(20.0)


def test_slippage_moves_fill_price_against_you():
    result = run_backtest(make_prices(), AllInThenOut(), initial_cash=1000,
                          fee_fn=flat_fee, slippage_bps=100)
    buy, sell = result.trades
    assert buy.fill_price == pytest.approx(10.0 * 1.01)   # buys fill higher
    assert sell.fill_price == pytest.approx(13.0 * 0.99)  # sells fill lower


class SpyStrategy:
    """Records the last date it was allowed to see at every call."""
    def __init__(self):
        self.seen = []

    def target_weights(self, closes):
        self.seen.append((len(closes), closes.index[-1]))
        return None


def test_no_lookahead_strategy_only_sees_data_up_to_today():
    spy = SpyStrategy()
    run_backtest(make_prices(), spy, initial_cash=1000,
                 fee_fn=flat_fee, slippage_bps=0)
    dates = make_prices()["A"].index
    # Called once per day, and on day i it saw exactly the first i+1 rows.
    assert [(n, d) for n, d in spy.seen] == [(i + 1, dates[i]) for i in range(4)]


def test_stats_computed():
    result = run_backtest(make_prices(), AllInThenOut(), initial_cash=1000,
                          fee_fn=flat_fee, slippage_bps=0)
    assert result.stats["total_return_pct"] == pytest.approx(27.7)
    assert result.stats["max_dd_pct"] == pytest.approx(0.0)
    assert result.stats["n_trades"] == 2
