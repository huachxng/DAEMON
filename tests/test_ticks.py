"""SET tick-size table and stop-price rounding — hand-computed:
  <2: 0.01 · 2-5: 0.02 · 5-10: 0.05 · 10-25: 0.10 · 25-100: 0.25 · 100-200: 0.50
  Stops round DOWN to a valid tick (a sell trigger slightly lower is safe;
  an invalid price is rejected by the exchange).
    4.2921 (band 2-5, tick .02) -> 4.28
   16.0500 (band 10-25, tick .10) -> 16.00
   40.5333 (band 25-100, tick .25) -> 40.50
    1.7649 (band <2, tick .01)  -> 1.76
"""
import pytest

from src.portfolio.ticks import set_tick, round_down_to_tick


@pytest.mark.parametrize("price,tick", [
    (1.50, 0.01), (3.00, 0.02), (7.00, 0.05), (15.0, 0.10), (50.0, 0.25), (150.0, 0.50),
])
def test_tick_bands(price, tick):
    assert set_tick(price) == tick


@pytest.mark.parametrize("raw,expected", [
    (4.2921, 4.28), (16.05, 16.00), (40.5333, 40.50), (1.7649, 1.76),
])
def test_round_down_to_tick(raw, expected):
    assert round_down_to_tick(raw) == pytest.approx(expected)
