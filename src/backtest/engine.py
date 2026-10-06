"""Event-driven daily backtest engine.

Honesty rules, enforced by construction:
- The strategy sees closes up to and including "today" — never tomorrow.
- Decisions made on today's close FILL AT TOMORROW'S OPEN (you cannot trade a
  price you only know after the market closed).
- Slippage always works against you: buys fill higher, sells fill lower.
- Fees are charged on every fill via the injected fee function.
"""
import math
from dataclasses import dataclass, field

import pandas as pd

from src.risk.metrics import max_drawdown


@dataclass
class Fill:
    date: object
    ticker: str
    side: str
    qty: float
    fill_price: float
    fee: float


@dataclass
class BacktestResult:
    equity: pd.Series = None
    trades: list = field(default_factory=list)
    fees_paid: float = 0.0
    stats: dict = field(default_factory=dict)


def run_backtest(prices: dict, strategy, initial_cash: float,
                 fee_fn, slippage_bps: float) -> BacktestResult:
    """prices: {ticker: DataFrame(open, close) indexed by date}."""
    closes = pd.DataFrame({t: df["close"] for t, df in prices.items()}).sort_index()
    opens = pd.DataFrame({t: df["open"] for t, df in prices.items()}).sort_index()
    dates = closes.index

    cash = initial_cash
    held: dict = {}                  # ticker -> qty
    pending: dict | None = None      # target weights awaiting next open
    result = BacktestResult()
    equity_curve = []
    slip = slippage_bps / 10_000.0

    for i, today in enumerate(dates):
        # 1) Fill yesterday's decision at TODAY's open.
        if pending is not None:
            open_px = opens.loc[today]
            equity_at_open = cash + sum(
                q * open_px[t] for t, q in held.items() if not math.isnan(open_px[t])
            )
            # Sells first (frees cash), then buys.
            deltas = {}
            for ticker, weight in pending.items():
                px = open_px.get(ticker)
                if px is None or math.isnan(px):
                    continue
                target_qty = math.floor(weight * equity_at_open / px)
                deltas[ticker] = target_qty - held.get(ticker, 0)
            for ticker, delta in sorted(deltas.items(), key=lambda kv: kv[1]):
                px = open_px[ticker]
                if delta < 0:
                    fill_px = px * (1 - slip)
                    fee = fee_fn(-delta * fill_px, -delta)
                    cash += -delta * fill_px - fee
                    held[ticker] = held.get(ticker, 0) + delta
                    result.trades.append(Fill(today, ticker, "SELL", -delta, fill_px, fee))
                    result.fees_paid += fee
                elif delta > 0:
                    fill_px = px * (1 + slip)
                    qty = delta
                    while qty > 0 and qty * fill_px + fee_fn(qty * fill_px, qty) > cash:
                        qty -= 1
                    if qty <= 0:
                        continue
                    fee = fee_fn(qty * fill_px, qty)
                    cash -= qty * fill_px + fee
                    held[ticker] = held.get(ticker, 0) + qty
                    result.trades.append(Fill(today, ticker, "BUY", qty, fill_px, fee))
                    result.fees_paid += fee
            held = {t: q for t, q in held.items() if q != 0}
            pending = None

        # 2) Mark to market at today's close.
        close_px = closes.loc[today]
        equity = cash + sum(
            q * close_px[t] for t, q in held.items() if not math.isnan(close_px[t])
        )
        equity_curve.append(equity)

        # 3) Ask the strategy, showing ONLY data up to today.
        decision = strategy.target_weights(closes.iloc[: i + 1])
        if decision is not None and i < len(dates) - 1:
            pending = decision

    result.equity = pd.Series(equity_curve, index=dates)
    rets = result.equity.pct_change().dropna()
    years = len(dates) / 252
    total = result.equity.iloc[-1] / initial_cash - 1
    result.stats = {
        "total_return_pct": round(100 * total, 1),
        "cagr_pct": round(100 * ((1 + total) ** (1 / years) - 1), 1) if years > 0.5 else None,
        "max_dd_pct": round(-100 * max_drawdown(result.equity), 1),
        "sharpe": round(float(rets.mean() / rets.std() * (252 ** 0.5)), 2) if rets.std() > 0 else None,
        "n_trades": len(result.trades),
        "fees_paid": round(result.fees_paid, 2),
    }
    return result
