"""Value a book of positions at the latest known prices."""
from dataclasses import dataclass, field


@dataclass
class Row:
    ticker: str
    qty: float
    cost_basis: float
    last_price: float
    value: float
    unrealized: float
    weight_pct: float = 0.0


@dataclass
class BookSummary:
    rows: list = field(default_factory=list)
    total_value: float = 0.0
    total_cost: float = 0.0
    total_unrealized: float = 0.0
    total_realized: float = 0.0


def summarize_book(positions: dict, last_prices: dict) -> BookSummary:
    """positions: {ticker: Position} from the ledger; last_prices: {ticker: float}."""
    s = BookSummary()
    for ticker, pos in sorted(positions.items()):
        s.total_realized += pos.realized_pl
        if pos.qty <= 0:
            continue
        price = last_prices.get(ticker)
        if price is None:
            raise KeyError(f"no last price for held position {ticker}")
        row = Row(
            ticker=ticker,
            qty=pos.qty,
            cost_basis=pos.cost_basis,
            last_price=price,
            value=pos.qty * price,
            unrealized=pos.unrealized_pl(price),
        )
        s.rows.append(row)
        s.total_value += row.value
        s.total_cost += row.cost_basis
        s.total_unrealized += row.unrealized
    for row in s.rows:
        row.weight_pct = 100.0 * row.value / s.total_value if s.total_value else 0.0
    return s
