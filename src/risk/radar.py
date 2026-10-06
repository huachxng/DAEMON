"""News/event radar — deterministic triggers that decide when the morning run
is ALLOWED to spend web searches. Quiet day = no triggers = zero web cost.
"""
from datetime import date, timedelta

MOVE_PCT = 3.0          # underlying daily move worth explaining
EARNINGS_WINDOW = 5     # trading days of advance warning


def move_trigger(name, prev_close, close):
    pct = 100 * (close / prev_close - 1)
    if abs(pct) >= MOVE_PCT:
        return f"MOVE {name} {pct:+.1f}% last session — explain why"
    return None


def trading_days_until(today_iso: str, event_iso: str) -> int:
    d, end = date.fromisoformat(today_iso), date.fromisoformat(event_iso)
    n = 0
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def earnings_trigger(name, earnings_iso, today):
    if earnings_iso < today:
        return None
    n = trading_days_until(today, earnings_iso)
    if n <= EARNINGS_WINDOW:
        return (f"EARNINGS {name} reports {earnings_iso} "
                f"({n} trading day{'s' if n != 1 else ''} away)")
    return None
