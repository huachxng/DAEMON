"""Pure risk math on pandas Series. No database, no I/O.

Conventions:
- price/equity curves are pd.Series indexed by date
- return series are daily simple returns (pct change)
- all pairwise stats align on common dates first (inner join)
"""
import pandas as pd


def returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()


def max_drawdown(curve: pd.Series) -> float:
    """Worst peak-to-trough drop, as a negative fraction (0.0 = never fell)."""
    running_peak = curve.cummax()
    drawdowns = curve / running_peak - 1.0
    return float(drawdowns.min())


def beta(asset_returns: pd.Series, bench_returns: pd.Series) -> float:
    """cov(asset, bench) / var(bench) on their overlapping dates."""
    joined = pd.concat([asset_returns, bench_returns], axis=1, join="inner").dropna()
    a, b = joined.iloc[:, 0], joined.iloc[:, 1]
    return float(a.cov(b) / b.var())


def correlation_matrix(return_series: dict) -> pd.DataFrame:
    """Pairwise correlations, aligned on common dates per pair."""
    df = pd.DataFrame(return_series)
    return df.corr()


def proforma_equity(quantities: dict, prices: dict) -> pd.Series:
    """Value of holding today's quantities across the whole price history.

    'Pro-forma': pretends the current portfolio was held constant — used to
    ask "how would THIS portfolio have behaved?", not to report actual history.
    """
    values = pd.DataFrame({t: prices[t] * q for t, q in quantities.items()})
    return values.dropna().sum(axis=1)
