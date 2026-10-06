"""Per-position protective exits for the LIVE sleeve.

Four exit layers, checked in this order of urgency:
  1. hard_stop    — DR closes at/below 80% of avg cost. Non-negotiable.
  2. trend_break  — the US underlying closes below its 200-day SMA.
  3. (strategy)   — name drops out of the top-5 at the quarterly re-pick.
  4. (book)       — breaker ladder: halt buys <=160k, liquidate <=155k.
Layers 3-4 live in paperbot/bot.py; this module is the daily per-name check.
"""

HARD_STOP_FRAC = 0.80   # exit at -20% from cost


def exit_signal(cost_per_unit, dr_close, u_close, u_sma200,
                hard_stop_frac=HARD_STOP_FRAC):
    """Return 'hard_stop', 'trend_break', or None for one held position."""
    if dr_close <= cost_per_unit * hard_stop_frac:
        return "hard_stop"
    if u_close is not None and u_sma200 is not None and u_close < u_sma200:
        return "trend_break"
    return None
