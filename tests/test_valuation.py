"""Book valuation — hand-computed:
  A: 100 shares @ cost 1000 total, last price 12 -> value 1200, unrealized +200
  B: 50 shares  @ cost 400 total,  last price  6 -> value  300, unrealized -100
  Book market value = 1500; weights: A 80%, B 20%.
"""
import pytest

from src.portfolio.ledger import Trade, build_positions
from src.portfolio.valuation import summarize_book


def test_summary_values_and_weights():
    trades = [
        Trade("real", "A", "BUY", 100, 10.0, 0.0, "2026-08-01"),
        Trade("real", "B", "BUY", 50, 8.0, 0.0, "2026-08-01"),
    ]
    positions = build_positions(trades)
    summary = summarize_book(positions, last_prices={"A": 12.0, "B": 6.0})

    assert summary.total_value == pytest.approx(1500.0)
    assert summary.total_unrealized == pytest.approx(100.0)
    rows = {r.ticker: r for r in summary.rows}
    assert rows["A"].weight_pct == pytest.approx(80.0)
    assert rows["B"].unrealized == pytest.approx(-100.0)


def test_closed_positions_excluded_from_rows_but_realized_kept():
    trades = [
        Trade("real", "A", "BUY", 100, 10.0, 0.0, "2026-08-01"),
        Trade("real", "A", "SELL", 100, 11.0, 0.0, "2026-08-02"),
    ]
    summary = summarize_book(build_positions(trades), last_prices={"A": 12.0})
    assert summary.rows == []
    assert summary.total_realized == pytest.approx(100.0)
    assert summary.total_value == 0.0
