"""The 'set these in Streaming' card: per-position cut-loss triggers, tick-valid.

Cut-loss = hard stop (80% of avg cost) rounded DOWN to a valid SET tick — ready
to enter as a Conditional SELL. Trend level = the underlying's SMA200 mapped
into DR price (approx, FX drifts) — an alert level, not an order to pre-place.
There is deliberately NO fixed take-profit: winners leave via momentum rotation
or trend break, never because they went up.
"""
from src.config import load_universe
from src.paperbot.bot import paper_snapshot
from src.portfolio.ticks import round_down_to_tick

# Planned costs for orders still working at the broker (from the user's limits).
# Keyed on the daemon's pending ticket, so the row disappears once the fill is
# logged and the ticket clears. A name can be HELD and WORKING at the same time
# (adding to a position). Update this when the user places/cancels an order.
WORKING_LIMITS = {}   # legacy default; live values are in DB state 'working_limits'


def working_limits(store, defaults=None) -> dict:
    """Limits of orders currently working at the broker: DB state wins, else defaults.
    Updated through record_working_order() (from scripts/log_order.py), so the
    email hub's 'placed ...' / 'cancelled ...' replies flow into every page."""
    import json
    raw = store.get_state("working_limits")
    if raw:
        return json.loads(raw)
    return dict(defaults if defaults is not None else WORKING_LIMITS)


def record_working_order(store, ticker, price, placed: bool) -> None:
    import json
    cur = working_limits(store, defaults={})
    if placed:
        cur[ticker] = price
    else:
        cur.pop(ticker, None)
    store.set_state("working_limits", json.dumps(cur))


def levels_rows(store, settings) -> list:
    uni = load_universe()
    snap = paper_snapshot(store, settings, book="live")
    u_of = {p["dr"]: p["underlying"] for p in uni["dr_map"]}

    def last_close(t):
        df = store.read_prices(t)
        df = df[df["close"].notna()]
        return float(df["close"].iloc[-1]) if not df.empty else None

    rows = []
    for r in snap["rows"]:
        cost_pu = (r["value"] - r["unrealized"]) / r["qty"]
        rows.append((r["ticker"], r["qty"], cost_pu, "HELD"))
    for o in snap["pending"]:
        wl = working_limits(store)
        if o["side"] == "BUY" and o["ticker"] in wl:
            rows.append((o["ticker"], o["qty"], wl[o["ticker"]], "WORKING"))

    out = []
    for ticker, qty, cost_pu, status in sorted(rows):
        stop = round_down_to_tick(cost_pu * 0.80)
        u = u_of.get(ticker)
        trend_dr = None
        if u:
            udf = store.read_prices(u)
            us = udf[udf["close"].notna()]["close"]
            dr_last = last_close(ticker)
            if len(us) >= 200 and dr_last:
                trend_dr = round_down_to_tick(
                    float(us.tail(200).mean()) * dr_last / float(us.iloc[-1]))
        out.append({"ticker": ticker.replace(".BK", ""), "qty": qty,
                    "cost": cost_pu, "stop": stop, "trend_dr": trend_dr,
                    "status": status})
    return out


def levels_table_html(store, settings) -> str:
    rows = ""
    for r in levels_rows(store, settings):
        trend = f"{r['trend_dr']:,.2f}" if r["trend_dr"] else "—"
        rows += (f"<tr><td><b>{r['ticker']}</b> <span class='sub'>({r['status']})</span></td>"
                 f"<td>{r['qty']:g}</td><td>{r['cost']:,.2f}</td>"
                 f"<td><b>{r['stop']:,.2f}</b></td><td>{trend}</td></tr>")
    return f"""
<p class="sub">🛑 <b>Set these as Conditional SELL triggers in Streaming /
ตั้งเป็นคำสั่ง Cond. ขายใน Streaming</b> — cut-loss prices are tick-valid, rounded down.
The trend level is an alert line (approx, moves with FX) — when the daemon confirms a
close below it, a SELL ticket is issued. No fixed take-profit by design: winners exit
via quarterly rotation or trend break / ไม่มีจุดขายทำกำไรตายตัว
ผู้ชนะจะออกเมื่อหมดโมเมนตัมหรือหลุดแนวโน้มเท่านั้น</p>
<table>
<tr><th>DR</th><th>Qty / จำนวน</th><th>Avg cost / ต้นทุน</th>
<th>Cut-loss trigger ฿ / จุดตัดขาดทุน</th><th>Trend alert ฿ / แนวโน้ม</th></tr>
{rows}
</table>"""
