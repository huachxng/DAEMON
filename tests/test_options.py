"""Black–Scholes — checked against canonical textbook values.

S=100, K=100, T=1y, r=5%, sigma=20% (the classic reference case):
  call price ~ 10.4506     put price ~ 5.5735
  call delta ~ 0.6368      put delta ~ -0.3632
  gamma      ~ 0.01876     vega (per 1.00 of vol) ~ 37.524
Put-call parity: C - P = S - K*exp(-rT) must hold to the cent.
"""
import pytest

from src.options.black_scholes import bs_price, bs_greeks


CASE = dict(spot=100.0, strike=100.0, t_years=1.0, rate=0.05, sigma=0.20)


def test_call_and_put_prices_match_textbook():
    assert bs_price(kind="C", **CASE) == pytest.approx(10.4506, abs=1e-3)
    assert bs_price(kind="P", **CASE) == pytest.approx(5.5735, abs=1e-3)


def test_put_call_parity():
    import math
    c = bs_price(kind="C", **CASE)
    p = bs_price(kind="P", **CASE)
    assert c - p == pytest.approx(100 - 100 * math.exp(-0.05), abs=1e-9)


def test_greeks_match_textbook():
    g = bs_greeks(kind="C", **CASE)
    assert g["delta"] == pytest.approx(0.6368, abs=1e-3)
    assert g["gamma"] == pytest.approx(0.01876, abs=1e-4)
    assert g["vega"] == pytest.approx(37.524, abs=1e-2)
    put = bs_greeks(kind="P", **CASE)
    assert put["delta"] == pytest.approx(-0.3632, abs=1e-3)


def test_deep_itm_call_delta_approaches_one():
    g = bs_greeks(kind="C", spot=200.0, strike=100.0, t_years=0.25, rate=0.05, sigma=0.2)
    assert g["delta"] > 0.999
