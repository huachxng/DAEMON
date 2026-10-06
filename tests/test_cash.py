"""Cash after trades — hand-computed:
  start 1000, BUY 10@50 fee 5 -> -505, SELL 5@60 fee 3 -> +297  => 792.
"""
import pytest

from src.portfolio.ledger import Trade, cash_after_trades


def test_cash_after_trades_hand_case():
    trades = [
        Trade("paper", "A", "BUY", 10, 50.0, 5.0, "2026-08-01"),
        Trade("paper", "A", "SELL", 5, 60.0, 3.0, "2026-08-02"),
    ]
    assert cash_after_trades(1000.0, trades) == pytest.approx(792.0)
