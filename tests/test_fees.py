"""Thai commission model — CALIBRATED from a real BLS contract note (2026-08-14):
  (total fee + VAT) / notional = 0.2215% per side, all-in.
  NO minimum: daemon fills MSFT01 17,834 -> 39.50 and TDEX 8,464 -> 18.75 are exactly
  0.2215% (2026-08-17). A ฿212 sell therefore costs ฿0.47, not ฿50.
  100,000 THB notional -> 221.50
"""
import pytest

from src.portfolio.fees import thai_fee


def test_thai_fee_matches_calibrated_rate():
    assert thai_fee(50_000) == pytest.approx(110.75, abs=0.01)


def test_thai_fee_percentage_above_minimum():
    assert thai_fee(100_000) == pytest.approx(221.5)


def test_thai_fee_has_no_minimum():
    assert thai_fee(10_000) == pytest.approx(22.15)
    assert thai_fee(212) == pytest.approx(0.47, abs=0.005)
