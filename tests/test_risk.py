"""Risk math — hand-computed:

Max drawdown of [100, 120, 90, 110]:
  peak before trough = 120, trough = 90 -> 90/120 - 1 = -25%.

Beta: if asset returns are exactly 2x the benchmark's every day,
  beta = cov(2x, x)/var(x) = 2. Correlation = 1.

Pro-forma equity: hold 10 shares of A (prices 10, 11) and 100 of B (prices 2, 1.9):
  day1 = 10*10 + 100*2   = 300
  day2 = 10*11 + 100*1.9 = 300  -> flat curve, max drawdown 0.
"""
import pandas as pd
import pytest

from src.risk.metrics import max_drawdown, beta, correlation_matrix, proforma_equity


def idx(n):
    return pd.date_range("2026-01-01", periods=n, freq="D")


def test_max_drawdown_hand_case():
    curve = pd.Series([100.0, 120.0, 90.0, 110.0], index=idx(4))
    assert max_drawdown(curve) == pytest.approx(-0.25)


def test_max_drawdown_of_monotonic_rise_is_zero():
    curve = pd.Series([100.0, 101.0, 102.0], index=idx(3))
    assert max_drawdown(curve) == pytest.approx(0.0)


def test_beta_of_doubled_returns_is_two():
    bench = pd.Series([0.01, -0.02, 0.015, 0.005, -0.01], index=idx(5))
    asset = bench * 2
    assert beta(asset, bench) == pytest.approx(2.0)


def test_correlation_matrix_signs():
    a = pd.Series([0.01, -0.02, 0.015, 0.005, -0.01], index=idx(5))
    m = correlation_matrix({"A": a, "B": a * 3, "C": -a})
    assert m.loc["A", "B"] == pytest.approx(1.0)
    assert m.loc["A", "C"] == pytest.approx(-1.0)


def test_proforma_equity_hand_case():
    prices = {
        "A": pd.Series([10.0, 11.0], index=idx(2)),
        "B": pd.Series([2.0, 1.9], index=idx(2)),
    }
    curve = proforma_equity({"A": 10, "B": 100}, prices)
    assert list(curve) == [300.0, 300.0]
    assert max_drawdown(curve) == pytest.approx(0.0)


def test_beta_handles_misaligned_dates():
    bench = pd.Series([0.01, -0.02, 0.015, 0.005], index=idx(4))
    asset = (bench * 2)[1:]  # asset missing the first day
    assert beta(asset, bench) == pytest.approx(2.0)
