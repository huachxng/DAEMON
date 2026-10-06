"""Black–Scholes pricing and greeks. Pure math, no dependencies beyond stdlib.

Conventions: t_years in years, rate and sigma as decimals (0.05 = 5%),
vega per 1.00 change in sigma, theta per year (divide by 365 for per-day).
"""
import math


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(spot, strike, t_years, rate, sigma):
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma ** 2) * t_years) / (
        sigma * math.sqrt(t_years))
    return d1, d1 - sigma * math.sqrt(t_years)


def bs_price(kind, spot, strike, t_years, rate, sigma) -> float:
    d1, d2 = _d1_d2(spot, strike, t_years, rate, sigma)
    disc = strike * math.exp(-rate * t_years)
    if kind == "C":
        return spot * _norm_cdf(d1) - disc * _norm_cdf(d2)
    return disc * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def bs_greeks(kind, spot, strike, t_years, rate, sigma) -> dict:
    d1, d2 = _d1_d2(spot, strike, t_years, rate, sigma)
    pdf = _norm_pdf(d1)
    delta = _norm_cdf(d1) if kind == "C" else _norm_cdf(d1) - 1.0
    disc = strike * math.exp(-rate * t_years)
    theta_common = -spot * pdf * sigma / (2.0 * math.sqrt(t_years))
    if kind == "C":
        theta = theta_common - rate * disc * _norm_cdf(d2)
    else:
        theta = theta_common + rate * disc * _norm_cdf(-d2)
    return {
        "delta": delta,
        "gamma": pdf / (spot * sigma * math.sqrt(t_years)),
        "vega": spot * pdf * math.sqrt(t_years),
        "theta": theta,
    }
