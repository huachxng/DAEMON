"""Assemble the risk picture for a book from the store.

Everything here is derived data for the report: weights come from the
valuation, stats from src/risk/metrics, sector/geo labels from universe.yaml.
"""
import pandas as pd

from src.config import load_universe
from src.portfolio.ledger import build_positions
from src.portfolio.valuation import summarize_book
from src.risk.metrics import returns, max_drawdown, beta, correlation_matrix, proforma_equity


def _price_series(store, ticker, column="adj_close") -> pd.Series:
    df = store.read_prices(ticker)
    s = pd.Series(df[column].values, index=pd.to_datetime(df["date"]), name=ticker)
    return s[s > 0]


def risk_summary(store, settings, book="real", lookback_days=252) -> dict:
    uni = load_universe()
    meta = {h["yahoo"]: h for h in uni["real_holdings"] if h.get("yahoo")}

    positions = build_positions(store.read_trades(book))
    held = {t: p.qty for t, p in positions.items() if p.qty > 0}
    if not held:
        return {"empty": True}

    prices = {t: _price_series(store, t) for t in held}
    last_prices = {t: float(s.iloc[-1]) for t, s in prices.items()}
    summary = summarize_book(positions, last_prices)
    weights = {r.ticker: r.weight_pct for r in summary.rows}

    rets = {t.replace(".BK", ""): returns(s.tail(lookback_days)) for t, s in prices.items()}
    corr = correlation_matrix(rets).round(2)

    bench_set = returns(_price_series(store, uni["benchmarks"]["set_fallback"]).tail(lookback_days))
    bench_us = returns(_price_series(store, uni["benchmarks"]["us"]).tail(lookback_days))
    betas = {
        t.replace(".BK", ""): {
            "set": round(beta(returns(s.tail(lookback_days)), bench_set), 2),
            "us": round(beta(returns(s.tail(lookback_days)), bench_us), 2),
        }
        for t, s in prices.items()
    }

    curve = proforma_equity(held, prices).tail(lookback_days)
    current_dd = float(curve.iloc[-1] / curve.max() - 1.0)

    exposure = {"geo": {}, "sector": {}}
    for t, w in weights.items():
        info = meta.get(t, {})
        for key in ("geo", "sector"):
            label = info.get(key, "Unknown")
            exposure[key][label] = exposure[key].get(label, 0.0) + w

    threshold = 25.0  # keep in sync with rules.yaml concentration threshold
    return {
        "empty": False,
        "weights": weights,
        "concentration_breaches": {t: w for t, w in weights.items() if w > threshold},
        "corr": corr,
        "betas": betas,
        "proforma_max_dd": max_drawdown(curve),
        "proforma_current_dd": current_dd,
        "curve_days": len(curve),
        "exposure": exposure,
    }
