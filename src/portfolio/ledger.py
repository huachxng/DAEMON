"""FIFO lot accounting.

The rules, in plain language:
- Every BUY opens a "lot": its cost = qty * price + the buy fee.
- Every SELL consumes the OLDEST lots first (First In, First Out).
- Realized P&L on a sell = (proceeds - sell fee) - cost of the shares consumed.
- Cost basis of what's left = the surviving lots' costs.

Pure functions, no database — the DB layer feeds Trade objects in.
"""
from dataclasses import dataclass, field


@dataclass
class Trade:
    book: str          # 'real' or 'paper'
    ticker: str
    side: str          # 'BUY' or 'SELL'
    qty: float
    price: float
    fees: float
    ts: str            # ISO date/datetime, used for ordering
    note: str = ""


@dataclass
class Lot:
    qty: float
    cost_total: float  # includes the buy fee for this lot

    @property
    def cost_per_share(self) -> float:
        return self.cost_total / self.qty


@dataclass
class Position:
    ticker: str
    lots: list = field(default_factory=list)
    realized_pl: float = 0.0

    @property
    def qty(self) -> float:
        return sum(lot.qty for lot in self.lots)

    @property
    def cost_basis(self) -> float:
        return sum(lot.cost_total for lot in self.lots)

    def unrealized_pl(self, market_price: float) -> float:
        return self.qty * market_price - self.cost_basis


def cash_after_trades(start_cash: float, trades: list) -> float:
    """Replay cash flows: buys cost qty*price+fees, sells return qty*price-fees."""
    cash = start_cash
    for t in trades:
        if t.side == "BUY":
            cash -= t.qty * t.price + t.fees
        else:
            cash += t.qty * t.price - t.fees
    return cash


def build_positions(trades: list) -> dict:
    """Replay all trades in timestamp order and return {ticker: Position}."""
    positions: dict = {}
    for t in sorted(trades, key=lambda t: t.ts):
        pos = positions.setdefault(t.ticker, Position(ticker=t.ticker))
        if t.side == "BUY":
            pos.lots.append(Lot(qty=t.qty, cost_total=t.qty * t.price + t.fees))
        elif t.side == "SELL":
            if t.qty > pos.qty + 1e-9:
                raise ValueError(
                    f"{t.ticker}: selling {t.qty} is more than held ({pos.qty})"
                )
            proceeds = t.qty * t.price - t.fees
            remaining = t.qty
            cost_consumed = 0.0
            while remaining > 1e-9:
                lot = pos.lots[0]
                take = min(lot.qty, remaining)
                cost_consumed += take * lot.cost_per_share
                lot.cost_total -= take * lot.cost_per_share
                lot.qty -= take
                remaining -= take
                if lot.qty <= 1e-9:
                    pos.lots.pop(0)
            pos.realized_pl += proceeds - cost_consumed
        else:
            raise ValueError(f"unknown trade side: {t.side!r}")
    return positions


def realized_history(trades: list) -> list:
    """Per-sale realized P&L, FIFO — one entry per SELL, for the track record.

    Same rules as build_positions; kept separate so each stays simple to read.
    """
    events = []
    lots: dict = {}
    for t in sorted(trades, key=lambda t: t.ts):
        book_lots = lots.setdefault(t.ticker, [])
        if t.side == "BUY":
            book_lots.append(Lot(qty=t.qty, cost_total=t.qty * t.price + t.fees))
            continue
        proceeds = t.qty * t.price - t.fees
        remaining, cost_consumed = t.qty, 0.0
        while remaining > 1e-9 and book_lots:
            lot = book_lots[0]
            take = min(lot.qty, remaining)
            cost_consumed += take * lot.cost_per_share
            lot.cost_total -= take * lot.cost_per_share
            lot.qty -= take
            remaining -= take
            if lot.qty <= 1e-9:
                book_lots.pop(0)
        events.append({"ts": t.ts, "ticker": t.ticker, "qty": t.qty,
                       "proceeds": proceeds, "cost": cost_consumed,
                       "pl": proceeds - cost_consumed})
    return events
