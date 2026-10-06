"""FIFO lot accounting — verified against hand-computed examples.

Hand-computed reference case used throughout:
  Buy  100 @ 10.00, fee 20  -> lot cost 1020 (10.20/share)
  Buy  100 @ 12.00, fee 20  -> lot cost 1220 (12.20/share)
  Sell 150 @ 13.00, fee 30  -> proceeds 1950 - 30 = 1920
      FIFO consumes: 100 @ 10.20 (1020) + 50 @ 12.20 (610) = 1630 cost
      Realized P&L = 1920 - 1630 = +290
  Remaining: 50 shares, cost 610 (12.20/share)
      At market 13.00 -> value 650, unrealized +40
"""
import pytest

from src.portfolio.ledger import Trade, build_positions


def reference_trades():
    return [
        Trade(book="real", ticker="TEST", side="BUY", qty=100, price=10.0, fees=20.0, ts="2026-08-01"),
        Trade(book="real", ticker="TEST", side="BUY", qty=100, price=12.0, fees=20.0, ts="2026-08-02"),
        Trade(book="real", ticker="TEST", side="SELL", qty=150, price=13.0, fees=30.0, ts="2026-08-03"),
    ]


def test_fifo_realized_pl_matches_hand_computation():
    positions = build_positions(reference_trades())
    pos = positions["TEST"]
    assert pos.realized_pl == pytest.approx(290.0)


def test_remaining_lot_qty_and_cost():
    pos = build_positions(reference_trades())["TEST"]
    assert pos.qty == 50
    assert pos.cost_basis == pytest.approx(610.0)


def test_unrealized_pl_at_market_price():
    pos = build_positions(reference_trades())["TEST"]
    assert pos.unrealized_pl(market_price=13.0) == pytest.approx(40.0)


def test_selling_more_than_held_raises():
    trades = [
        Trade(book="real", ticker="TEST", side="BUY", qty=10, price=10.0, fees=0.0, ts="2026-08-01"),
        Trade(book="real", ticker="TEST", side="SELL", qty=11, price=10.0, fees=0.0, ts="2026-08-02"),
    ]
    with pytest.raises(ValueError, match="more than held"):
        build_positions(trades)


def test_fully_closed_position_keeps_realized_pl():
    trades = [
        Trade(book="real", ticker="NVDA01", side="BUY", qty=100, price=20.0, fees=10.0, ts="2026-07-01"),
        Trade(book="real", ticker="NVDA01", side="SELL", qty=100, price=22.0, fees=12.0, ts="2026-08-01"),
    ]
    pos = build_positions(trades)["NVDA01"]
    # proceeds 2200-12=2188, cost 2010 -> +178
    assert pos.qty == 0
    assert pos.realized_pl == pytest.approx(178.0)


def test_trades_processed_in_timestamp_order_even_if_given_shuffled():
    shuffled = list(reversed(reference_trades()))
    pos = build_positions(shuffled)["TEST"]
    assert pos.realized_pl == pytest.approx(290.0)
