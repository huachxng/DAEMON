"""Stop-watch: warn within 5% of the cut-loss, breach at/below it — hand-computed:
  stop 15.90: last 16.90 -> none (6.3% above) · 16.60 -> warn (4.4%) · 15.90 -> breach
Dedupe: same level per ticker per day fires once; escalation warn->breach fires again.
"""
from src.risk.stop_watch import proximity, should_notify


def test_proximity_bands():
    assert proximity(last=16.90, stop=15.90) is None
    assert proximity(last=16.60, stop=15.90) == "warn"
    assert proximity(last=15.90, stop=15.90) == "breach"
    assert proximity(last=15.00, stop=15.90) == "breach"


def test_dedupe_once_per_day_with_escalation():
    sent = {}
    assert should_notify(sent, "MICRON01.BK", "warn", "2026-08-25") is True
    assert should_notify(sent, "MICRON01.BK", "warn", "2026-08-25") is False
    assert should_notify(sent, "MICRON01.BK", "breach", "2026-08-25") is True   # escalation
    assert should_notify(sent, "MICRON01.BK", "breach", "2026-08-25") is False
    assert should_notify(sent, "MICRON01.BK", "warn", "2026-08-26") is True     # new day
