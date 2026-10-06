"""Turn target weights into concrete orders, with board-lot rounding.

All prices arrive in THB (US names pre-converted by the caller), so the
sizing math is single-currency and boring — exactly how money math should be.
"""
from dataclasses import dataclass
import math


@dataclass
class Order:
    ticker: str
    side: str   # BUY / SELL
    qty: float


def pick_affordable(ranking: list, prices_thb: dict, slot_thb: float, n: int) -> list:
    """Walk the momentum ranking, keeping the first n names whose single share
    fits inside one slot. At ฿200k book scale, US mega-priced shares (ASML,
    LLY, MU) can cost more than a whole slot — substitute rather than hold cash."""
    picks = []
    for ticker in ranking:
        price = prices_thb.get(ticker)
        if price and price <= slot_thb:
            picks.append(ticker)
        if len(picks) == n:
            break
    return picks


def orders_from_targets(equity: float, targets: dict, held: dict,
                        prices_thb: dict, lot_sizes: dict) -> list:
    """Compare target position sizes with holdings and emit the difference.

    Rounding: down to the board lot (Thai ETFs/stocks trade in lots of 100);
    US names trade single shares. Drifts smaller than one lot are ignored.
    """
    orders = []
    for ticker, weight in targets.items():
        price = prices_thb.get(ticker)
        if not price or price <= 0 or math.isnan(price):
            continue
        lot = lot_sizes.get(ticker, 1)
        target_qty = math.floor(weight * equity / price / lot) * lot
        delta = target_qty - held.get(ticker, 0)
        if delta >= lot:
            orders.append(Order(ticker, "BUY", delta))
        elif delta <= -lot:
            orders.append(Order(ticker, "SELL", -delta))
    # Sells first so the fills free cash before buys execute.
    return sorted(orders, key=lambda o: 0 if o.side == "SELL" else 1)


def drop_dust(orders: list, prices_thb: dict, targets: dict, min_notional: float) -> list:
    """Drop trims too small to be worth a ticket, on BOTH sides.

    A full exit (target weight 0 — protective stop, rotation, liquidation) is
    never dust, whatever its size. Found the hard way: a ฿212 SELL trim on
    2026-08-20 that the user dutifully executed.
    """
    kept = []
    for o in orders:
        notional = o.qty * (prices_thb.get(o.ticker) or 0)
        full_exit = o.side == "SELL" and targets.get(o.ticker, 0) == 0
        if notional >= min_notional or full_exit:
            kept.append(o)
    return kept


def scale_targets(targets: dict, factor: float) -> dict:
    """Return a copy with every weight scaled — the graduated de-risk step."""
    return {t: w * factor for t, w in targets.items()}


def apply_user_overrides(orders: list, overrides: dict, protected: set) -> list:
    """Honour a user's 'hold' override on rotation SELLs. Never on protective
    exits (stop / trend break) or liquidation — those tickers arrive in
    `protected` and always get their SELL ticket."""
    return [o for o in orders
            if not (o.side == "SELL" and overrides.get(o.ticker) == "hold"
                    and o.ticker not in protected)]
