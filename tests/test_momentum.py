"""Top-N momentum strategy — hand-constructed:

Three tickers over Jan 28–Feb 2 (business days), lookback 3:
  A rises 10 -> 13   (+30% over lookback)
  B falls 10 -> 7    (-30%)
  C rises 10 -> 11   (+10%)
Decision fires only on the first trading day of a new month (Feb 2 here).
Top 2 of {A: +30%, C: +10%, B: -30%} -> A and C, equal weight 0.5 each.
"""
import pandas as pd

from src.backtest.momentum import TopNMomentum


def closes_frame():
    dates = pd.bdate_range("2026-01-28", "2026-02-02")  # Wed..Mon, 4 business days
    return pd.DataFrame({
        "A": [10.0, 11.0, 12.0, 13.0],
        "B": [10.0, 9.0, 8.0, 7.0],
        "C": [10.0, 10.5, 10.8, 11.0],
    }, index=dates)


def test_no_decision_mid_month():
    strat = TopNMomentum(n=2, lookback=3, sma_filter=None)
    assert strat.target_weights(closes_frame().iloc[:3]) is None  # still January


def test_month_boundary_picks_top_n_equal_weight():
    strat = TopNMomentum(n=2, lookback=3, sma_filter=None)
    weights = strat.target_weights(closes_frame())  # last row = Feb 2
    assert weights == {"A": 0.5, "C": 0.5, "B": 0.0}


def test_losers_go_to_cash_not_shorted():
    strat = TopNMomentum(n=2, lookback=3, sma_filter=None, min_momentum=0.2)
    weights = strat.target_weights(closes_frame())
    # C's +10% is below the 20% bar -> its slot stays in cash.
    assert weights == {"A": 0.5, "B": 0.0, "C": 0.0}


def test_rebalance_every_3_months_skips_other_month_boundaries():
    import pandas as pd
    strat = TopNMomentum(n=2, lookback=3, sma_filter=None, rebalance_every=3)
    # First month boundary seen -> acts (establishes the cycle)...
    assert strat.target_weights(closes_frame()) is not None
    # ...then a boundary 1 month later must be skipped.
    dates2 = pd.bdate_range("2026-02-25", "2026-03-02")[:4]
    frame2 = closes_frame().set_axis(dates2)
    assert strat.target_weights(frame2) is None


def test_insufficient_history_returns_none():
    strat = TopNMomentum(n=2, lookback=300, sma_filter=None)
    assert strat.target_weights(closes_frame()) is None
