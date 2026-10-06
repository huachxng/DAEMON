"""Settrade Open API — READ-ONLY sync of the real Bualuang account.

What this does:   pull portfolio / account / today's deals, compare with our
                  ledger, report differences (unlogged fills, ghosts).
What this NEVER does: place, change, or cancel an order. The SDK exposes those
                  methods; ReadOnlyEquity hides them behind a PermissionError so
                  a bug in our code cannot become a trade. This is a design
                  invariant of the whole project, tested in tests/.

Credentials live in config/settrade.yaml (git-ignored). The user creates that
file themselves; Claude never sees or asks for the values.

SDK facts (verified from settrade_v2 2.2.1 source, not docs):
  from settrade_v2 import Investor
  inv = Investor(app_id, app_secret, app_code, broker_id, is_auto_queue=False)
  eq  = inv.Equity(account_no)        # InvestorEquity
  eq.get_account_info() / get_portfolios() / get_orders() / get_trades()
  broker_id == "SANDBOX" -> uat environment, broker 098 (paper account).
"""
from pathlib import Path

import yaml

from src.config import PROJECT_ROOT

CREDENTIALS_PATH = PROJECT_ROOT / "config" / "settrade.yaml"
WRITE_METHODS = ("place_order", "change_order", "cancel_order", "cancel_orders")


class ReadOnlyEquity:
    """Wraps an InvestorEquity so only read methods are reachable."""

    def __init__(self, equity):
        self._eq = equity

    def __getattr__(self, name):
        if name in WRITE_METHODS:
            def _blocked(*a, **kw):
                raise PermissionError(
                    f"{name} blocked: CLAUDE TRADE's Settrade link is read-only "
                    "by design. Trades are executed by the user in Streaming."
                )
            return _blocked
        if not name.startswith("get_"):
            raise AttributeError(f"{name} is not exposed on the read-only link")
        return getattr(self._eq, name)


def load_credentials(path=CREDENTIALS_PATH):
    path = Path(path)
    if not path.exists():
        return None
    with open(path) as f:
        c = yaml.safe_load(f) or {}
    c["account_no"] = str(c.get("account_no", ""))
    return c


def connect(creds):
    """Return a ReadOnlyEquity for the configured account (imports SDK lazily)."""
    from settrade_v2 import Investor  # only needed when actually syncing

    inv = Investor(app_id=creds["app_id"], app_secret=creds["app_secret"],
                   app_code=creds["app_code"], broker_id=creds["broker_id"],
                   is_auto_queue=False)
    return ReadOnlyEquity(inv.Equity(creds["account_no"]))


def _unwrap_rows(payload):
    """The SDK hands back the raw JSON body. Depending on endpoint/version that
    is either a bare list or a dict wrapping the list (e.g. 'portfolioList').
    Accept both; find the first list-of-dicts inside a wrapper."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("portfolioList", "portfolios", "data", "items", "list"):
            if isinstance(payload.get(key), list):
                return payload[key]
        for v in payload.values():          # unknown key: any list of records
            if isinstance(v, list) and (not v or isinstance(v[0], dict)):
                return v
    return []


def normalize_portfolio(payload) -> dict:
    """SDK portfolio payload -> {yahoo_ticker: {qty, avg_price, market_price}}."""
    out = {}
    for r in _unwrap_rows(payload):
        if not isinstance(r, dict):
            continue
        sym = r.get("symbol") or r.get("symbolName") or r.get("securitySymbol")
        if not sym:
            continue
        out[f"{sym}.BK"] = {
            "qty": float(r.get("actualVolume") or r.get("availableVolume") or 0),
            "avg_price": float(r.get("averagePrice") or 0),
            "market_price": float(r.get("marketPrice") or 0),
        }
    return out


def reconcile(broker: dict, ledger_qty: dict) -> dict:
    """Compare broker holdings vs our combined ledger quantities.

    ledger_qty: {ticker: qty} summed across the personal ('real') and daemon
    ('live') books — the broker sees one account, we keep two ledgers.
    """
    matched, unlogged, missing = [], {}, {}
    for t, b in broker.items():
        ours = ledger_qty.get(t, 0)
        if abs(b["qty"] - ours) < 1e-9:
            matched.append(t)
        elif b["qty"] > ours:
            unlogged[t] = b["qty"] - ours
        else:
            missing[t] = ours - b["qty"]
    for t, q in ledger_qty.items():
        if t not in broker and q > 0:
            missing[t] = q
    return {"matched": sorted(matched), "unlogged": unlogged,
            "missing_at_broker": missing}
