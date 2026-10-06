"""Attribution — hand-computed, and it must reconcile to equity - start_cash.

Fixture book (start 200,000):
  A: BUY 100 @ 10, fee 5  -> later SELL 40 @ 12, fee 3   (realized: 40*12-3 - 40*10.05 = 75)
     remaining 60 @ 10.05 cost = 603; market 12 -> value 720, unrealized +117
  B: BUY 50 @ 20, fee 4   -> market 19 -> value 950, unrealized -54 (cost 1004)
  Fees total = 12. Cash = 200000 - 1005 - 1004 + 477 = 198468. Equity = 198468+720+950 = 200138.
  Sum of per-name (realized + unrealized) must equal equity - 200000 + fees... no:
  realized/unrealized are already net of fees, so sum(realized)+sum(unrealized)
  = 75 + 117 - 54 = 138 = equity - 200000. That identity is the test.
"""
import pytest

from src.portfolio.ledger import Trade
from src.risk.performance import attribution

TRADES = [
    Trade("live", "A", "BUY", 100, 10.0, 5.0, "2026-08-01"),
    Trade("live", "B", "BUY", 50, 20.0, 4.0, "2026-08-02"),
    Trade("live", "A", "SELL", 40, 12.0, 3.0, "2026-08-03"),
]
PRICES = {"A": 12.0, "B": 19.0}


def test_per_name_attribution_hand_computed():
    rows = {r["ticker"]: r for r in attribution(TRADES, PRICES)}
    assert rows["A"]["realized"] == pytest.approx(75.0)
    assert rows["A"]["unrealized"] == pytest.approx(117.0)
    assert rows["A"]["fees"] == pytest.approx(8.0)
    assert rows["B"]["unrealized"] == pytest.approx(-54.0)
    assert rows["B"]["fees"] == pytest.approx(4.0)


def test_attribution_reconciles_to_equity_change():
    rows = attribution(TRADES, PRICES)
    total = sum(r["realized"] + r["unrealized"] for r in rows)
    cash = 200_000 - (100*10+5) - (50*20+4) + (40*12-3)
    equity = cash + 60*12.0 + 50*19.0
    assert total == pytest.approx(equity - 200_000)
