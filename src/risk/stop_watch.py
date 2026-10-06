"""Intraday(ish) cut-loss watchdog.

The user's broker cannot hold conditional SELL orders on these DRs, so the
daemon watches delayed quotes instead (user request 2026-08-24). Bands:
  breach: last <= stop            -> urgent, SELL decision follows at EOD run
  warn:   last <= stop * 1.05     -> heads-up, once per ticker per day
Escalation warn->breach re-notifies; same level repeats are muted for the day.
"""
WARN_FRAC = 1.05


def proximity(last: float, stop: float):
    if last <= stop:
        return "breach"
    if last <= stop * WARN_FRAC:
        return "warn"
    return None


def should_notify(sent: dict, ticker: str, level: str, today: str) -> bool:
    """sent: mutable {ticker: {"date": d, "level": l}} persisted by the caller."""
    rank = {"warn": 1, "breach": 2}
    prev = sent.get(ticker)
    if prev and prev["date"] == today and rank[prev["level"]] >= rank[level]:
        return False
    sent[ticker] = {"date": today, "level": level}
    return True
