"""Per-name P&L attribution for the performance pack.

Identity that must always hold (tested): sum over names of
(realized + unrealized) == equity - start_cash, because both realized and
unrealized are computed net of fees through the FIFO ledger.
"""
from src.portfolio.ledger import build_positions, realized_history


def attribution(trades: list, last_prices: dict) -> list:
    """-> [{ticker, realized, unrealized, fees, qty}] sorted by total contribution."""
    positions = build_positions(trades)
    realized = {}
    for r in realized_history(trades):
        realized[r["ticker"]] = realized.get(r["ticker"], 0.0) + r["pl"]
    fees = {}
    for t in trades:
        fees[t.ticker] = fees.get(t.ticker, 0.0) + t.fees

    rows = []
    for ticker, pos in positions.items():
        unrl = pos.unrealized_pl(last_prices[ticker]) if pos.qty > 0 else 0.0
        rows.append({"ticker": ticker, "qty": pos.qty,
                     "realized": realized.get(ticker, 0.0),
                     "unrealized": unrl, "fees": fees.get(ticker, 0.0)})
    return sorted(rows, key=lambda r: -(r["realized"] + r["unrealized"]))
