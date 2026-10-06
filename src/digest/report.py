"""Bilingual (TH/EN) portfolio report as one self-contained HTML file."""
from datetime import datetime, timezone, timedelta

from src.config import load_universe
from src.digest.levels import levels_table_html
from src.portfolio.ledger import build_positions
from src.portfolio.valuation import summarize_book
from src.risk.dashboard import risk_summary

ICT = timezone(timedelta(hours=7))

CSS = """
body { font-family: -apple-system, 'Sukhumvit Set', sans-serif; margin: 2rem auto;
       max-width: 900px; color: #1a1a2e; background: #fafafa; padding: 0 1rem; }
h1 { font-size: 1.5rem; } h2 { font-size: 1.15rem; margin-top: 2rem; }
.sub { color: #666; font-size: 0.9rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.92rem; }
th, td { padding: 6px 10px; text-align: right; border-bottom: 1px solid #ddd; }
th { background: #1a1a2e; color: #fff; } td:first-child, th:first-child { text-align: left; }
tr.total td { font-weight: 700; border-top: 2px solid #1a1a2e; }
.pos { color: #0a7a2f; } .neg { color: #c0392b; }
.banner { background: #fff3cd; border: 1px solid #e0a800; border-radius: 6px;
          padding: 10px 14px; margin: 1rem 0; font-size: 0.9rem; }
.note { color: #666; font-size: 0.82rem; margin-top: 2rem; border-top: 1px solid #ddd;
        padding-top: 0.8rem; }
"""


def _fmt(x, dp=2):
    return f"{x:,.{dp}f}"


def _pl_cell(x):
    cls = "pos" if x >= 0 else "neg"
    return f'<td class="{cls}">{_fmt(x)}</td>'


def _risk_section(store, settings) -> str:
    r = risk_summary(store, settings, book="real")
    if r.get("empty"):
        return ""

    breach_html = ""
    for t, w in r["concentration_breaches"].items():
        breach_html += (
            f'<div class="banner">🚨 <b>{t.replace(".BK", "")}</b> is '
            f"{w:.1f}% of the book (limit 25%) / คิดเป็น {w:.1f}% ของพอร์ต "
            f"(เกินเพดาน 25%)</div>"
        )

    exp = r["exposure"]
    geo_line = " · ".join(f"{k}: {v:.0f}%" for k, v in
                          sorted(exp["geo"].items(), key=lambda kv: -kv[1]))
    sec_line = " · ".join(f"{k}: {v:.0f}%" for k, v in
                          sorted(exp["sector"].items(), key=lambda kv: -kv[1]))

    beta_rows = "".join(
        f"<tr><td>{t}</td><td>{b['set']}</td><td>{b['us']}</td></tr>"
        for t, b in sorted(r["betas"].items())
    )

    corr = r["corr"]
    corr_head = "".join(f"<th>{c}</th>" for c in corr.columns)
    corr_rows = ""
    for name, row in corr.iterrows():
        cells = "".join(
            f'<td style="background: rgba({"192,57,43" if v > 0.7 and c != name else "255,255,255"},0.12)">{v:.2f}</td>'
            for c, v in row.items()
        )
        corr_rows += f"<tr><td>{name}</td>{cells}</tr>"

    return f"""
<h2>Risk dashboard / แผงความเสี่ยง</h2>
{breach_html}
<p class="sub"><b>Geography / ภูมิศาสตร์:</b> {geo_line}<br>
<b>Sector / กลุ่มธุรกิจ:</b> {sec_line}<br>
<b>Pro-forma drawdown</b> (current holdings held constant, {r['curve_days']} trading days /
สมมติถือพอร์ตปัจจุบันคงที่): max {r['proforma_max_dd'] * 100:.1f}%,
now {r['proforma_current_dd'] * 100:.1f}% from peak / จากจุดสูงสุด</p>
<table style="width:auto"><tr><th>Beta vs</th><th>SET50 (TDEX)</th><th>S&amp;P 500</th></tr>
{beta_rows}</table>
<p class="sub" style="margin-top:1rem"><b>Correlation (1y daily) / สหสัมพันธ์:</b>
values above 0.7 mean the names tend to fall together / ค่าสูงกว่า 0.7 แปลว่ามักขึ้นลงพร้อมกัน</p>
<table style="width:auto"><tr><th></th>{corr_head}</tr>{corr_rows}</table>
<p class="sub">⚠️ DR caveat: SET closes before US markets open, so same-day correlations
and betas vs the S&amp;P understate how tightly these DRs actually track their US
underlyings. Treat the *economic* linkage as much higher than these numbers. /
ข้อควรระวัง: ตลาดไทยปิดก่อนตลาดสหรัฐเปิด ค่าสหสัมพันธ์รายวันจึงต่ำกว่าความเชื่อมโยงที่แท้จริง
DR เหล่านี้เคลื่อนไหวตามหุ้นแม่ในสหรัฐมากกว่าตัวเลขนี้มาก</p>
"""


def _paper_section(snap, store=None, live=False) -> str:
    state_labels = {
        "normal": "🟢 normal / ปกติ",
        "halt_buys": "🟡 HALT BUYS — de-risking / หยุดซื้อ กำลังลดความเสี่ยง",
        "liquidate": "🔴 LIQUIDATED — awaiting user review / ขายทั้งหมดแล้ว รอผู้ใช้ตรวจสอบ",
    }
    html = (f'<p class="sub">Equity / มูลค่าพอร์ต: <b>฿{_fmt(snap["equity"])}</b> '
            f'(cash ฿{_fmt(snap["cash"])} + positions ฿{_fmt(snap["value"])}) · '
            f'Realized P&L: ฿{_fmt(snap["realized"])} · '
            f'Circuit breaker / เบรกเกอร์: {state_labels[snap["state"]]}</p>')
    if snap["rows"]:
        rows = "".join(
            f"<tr><td>{r['ticker'].replace('.BK','')}</td><td>{_fmt(r['qty'], 0)}</td>"
            f"<td>{_fmt(r['price_thb'])}</td><td>{_fmt(r['value'])}</td>"
            f"{_pl_cell(r['unrealized'])}</tr>"
            for r in snap["rows"]
        )
        html += ("<table><tr><th>Ticker / หุ้น</th><th>Qty / จำนวน</th>"
                 "<th>Last ฿ / ราคา</th><th>Value ฿ / มูลค่า</th>"
                 "<th>Unrl. P&L ฿ / กำไรยังไม่ขาย</th></tr>" + rows + "</table>")
    if snap["pending"] and live:
        rows = ""
        total = 0.0
        for o in snap["pending"]:
            from src.paperbot.bot import _price_thb
            _, px = _price_thb(store, o["ticker"], "close", snap["fx"])
            est = o["qty"] * (px or 0)
            total += est
            rows += (f"<tr><td>🎫 <b>{o['side']}</b> {o['ticker'].replace('.BK','')}</td>"
                     f"<td>{o['qty']:g}</td><td>{_fmt(px or 0)}</td><td>{_fmt(est)}</td></tr>")
        html += (
            '<p class="sub">🎫 <b>Order tickets awaiting YOUR execution in Streaming / '
            'คำสั่งซื้อขายรอคุณส่งในแอป Streaming</b> — use limit orders near the last '
            'close; report fills back to Claude / ตั้งราคา limit ใกล้ราคาปิด '
            'แล้วแจ้งผลกลับมา</p>'
            "<table><tr><th>Ticket / คำสั่ง</th><th>Qty / จำนวน</th>"
            "<th>~Limit ฿ / ราคาแนะนำ</th><th>Est. cost ฿ / มูลค่าโดยประมาณ</th></tr>"
            + rows +
            f"<tr class='total'><td>Total / รวม</td><td></td><td></td><td>{_fmt(total)}</td></tr></table>"
        )
    elif snap["pending"]:
        pend = ", ".join(f"{o['side']} {o['qty']:g} {o['ticker'].replace('.BK','')}"
                         for o in snap["pending"])
        html += (f'<p class="sub">⏳ Pending (fills at next open / รอเปิดตลาด): {pend}</p>')
    return html


def _track_record_section(store) -> str:
    """Every order action + realized P&L for the LIVE sleeve — the day-60 record."""
    from src.portfolio.ledger import realized_history

    events = store.read_order_events("live")
    ev_rows = "".join(
        f"<tr><td>{e['ts'][:16]}</td><td>{e['event'].replace('_', ' ')}</td>"
        f"<td>{e['side']} {e['qty']:g} {e['ticker'].replace('.BK', '')}</td>"
        f"<td>{_fmt(e['price']) if e['price'] else '—'}</td></tr>"
        for e in reversed(events)
    ) or "<tr><td colspan='4'>—</td></tr>"

    realized = realized_history(store.read_trades("live"))
    rl_rows = "".join(
        f"<tr><td>{r['ts'][:10]}</td><td>{r['ticker'].replace('.BK', '')}</td>"
        f"<td>{r['qty']:g}</td><td>{_fmt(r['proceeds'])}</td><td>{_fmt(r['cost'])}</td>"
        f"{_pl_cell(r['pl'])}</tr>"
        for r in realized
    )
    total_pl = sum(r["pl"] for r in realized)
    realized_html = (
        "<table><tr><th>Date / วันที่</th><th>Ticker</th><th>Qty</th>"
        "<th>Proceeds ฿</th><th>Cost ฿</th><th>Earned/Lost ฿ / กำไร-ขาดทุน</th></tr>"
        + rl_rows +
        f"<tr class='total'><td>Total realized / รวมที่ขายแล้ว</td><td></td><td></td>"
        f"<td></td><td></td>{_pl_cell(total_pl)}</tr></table>"
        if realized else
        "<p class='sub'>No closed trades yet — realized P&L appears here after the "
        "first SELL. / ยังไม่มีรายการขาย กำไร-ขาดทุนจริงจะแสดงหลังขายครั้งแรก</p>"
    )

    curve = store.read_equity_history("live")
    curve_note = ""
    if curve:
        first, last = curve[0], curve[-1]
        curve_note = (f"<p class='sub'>Equity tracked daily since {first['date']}: "
                      f"฿{_fmt(first['equity'])} → ฿{_fmt(last['equity'])} "
                      f"({len(curve)} snapshots — full curve at the day-60 review) / "
                      f"บันทึกมูลค่าพอร์ตทุกวันเพื่อรีวิวตอนครบ 2 เดือน</p>")

    return (
        "<h2>📒 Track record — LIVE sleeve / บันทึกทุกคำสั่งซื้อขาย</h2>"
        "<p class='sub'>Append-only: every ticket, placement, fill, and cancel is "
        "recorded permanently for the two-month review. / บันทึกถาวรทุกรายการ "
        "เพื่อรีวิวร่วมกันตอนครบสองเดือน</p>"
        "<h3 style='font-size:.95rem'>Realized P&L / กำไร-ขาดทุนที่ขายแล้ว</h3>"
        + realized_html + curve_note +
        "<h3 style='font-size:.95rem'>Order log / บันทึกคำสั่ง</h3>"
        "<table><tr><th>When</th><th>Event</th><th>Order</th><th>Price ฿</th></tr>"
        + ev_rows + "</table>"
    )


def build_report(store, settings) -> str:
    uni = load_universe()
    dr_names = {h["yahoo"]: h["name"] for h in uni["real_holdings"] if h.get("yahoo")}

    real_trades = store.read_trades("real")
    has_placeholder = any("PLACEHOLDER" in t.note for t in real_trades)
    positions = build_positions(real_trades)
    held = [t for t, p in positions.items() if p.qty > 0]
    last_prices, freshness = {}, {}
    for t in set(held):
        df = store.read_prices(t)
        if not df.empty:
            last_prices[t] = float(df["close"].iloc[-1])
            freshness[t] = df["date"].iloc[-1]
    real = summarize_book(positions, last_prices)

    from src.paperbot.bot import paper_snapshot
    snap = paper_snapshot(store, settings)
    live_snap = paper_snapshot(store, settings, book="live")
    now = datetime.now(ICT).strftime("%Y-%m-%d %H:%M ICT")

    rows_html = ""
    for r in real.rows:
        rows_html += (
            f"<tr><td>{r.ticker.replace('.BK','')}<br>"
            f"<span class='sub'>{dr_names.get(r.ticker, '')}</span></td>"
            f"<td>{_fmt(r.qty, 0)}</td><td>{_fmt(r.cost_basis / r.qty)}</td>"
            f"<td>{_fmt(r.last_price)}</td><td>{_fmt(r.value)}</td>"
            f"{_pl_cell(r.unrealized)}<td>{_fmt(r.weight_pct, 1)}%</td></tr>"
        )
    floor = settings["books"]["real"]["alert_floor_thb"]
    real_cash = settings["books"]["real"].get("cash_balance_thb", 0)
    real_receivable = settings["books"]["real"].get("receivable_thb", 0)
    real_equity = real.total_value + real_cash + real_receivable

    banner = ""
    if has_placeholder:
        banner = (
            '<div class="banner">⚠️ <b>Placeholder cost basis / ต้นทุนโดยประมาณ:</b> '
            "positions were seeded at recent prices, NOT your actual fills. P&L below is "
            "meaningless until real fills are logged. — "
            "ราคาต้นทุนเป็นค่าประมาณ ยังไม่ใช่ราคาซื้อจริงของคุณ กำไร/ขาดทุนด้านล่างจึงยังไม่ถูกต้อง "
            "จนกว่าจะบันทึกรายการซื้อจริง</div>"
        )

    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CLAUDE TRADE — Portfolio Report</title><style>{CSS}</style></head><body>
<h1>📊 Portfolio Report / รายงานพอร์ตการลงทุน</h1>
<div class="sub">Generated {now} · Data: Yahoo Finance (EOD/delayed) · ข้อมูลสิ้นวัน (ล่าช้า)</div>
{banner}

<h2>REAL book — Bualuang (Streaming) / พอร์ตจริง</h2>
<table>
<tr><th>Ticker / หุ้น</th><th>Qty / จำนวน</th><th>Avg cost / ต้นทุนเฉลี่ย</th>
<th>Last / ราคาล่าสุด</th><th>Value ฿ / มูลค่า</th><th>Unrl. P&L ฿ / กำไรยังไม่ขาย</th><th>Weight / สัดส่วน</th></tr>
{rows_html}
<tr class="total"><td>Total / รวม</td><td></td><td></td><td></td>
<td>{_fmt(real.total_value)}</td>{_pl_cell(real.total_unrealized)}<td>100%</td></tr>
</table>
<p class="sub"><b>Account equity / มูลค่าบัญชีรวม: ฿{_fmt(real_equity)}</b> =
positions ฿{_fmt(real.total_value)} + cash ฿{_fmt(real_cash)} +
pending settlement ฿{_fmt(real_receivable)} (unsettled sale proceeds, T+2 / รอชำระราคา T+2) ·
Cut-loss line / เส้นตัดขาดทุน: ฿{_fmt(floor, 0)}
(equity is {_fmt(100 * real_equity / floor - 100, 1)}% above it /
สูงกว่าเส้น {_fmt(100 * real_equity / floor - 100, 1)}%)</p>

{_risk_section(store, settings)}

<h2>LIVE book — the daemon's real sleeve (you execute) / พอร์ตจริงของเดมอน (คุณเป็นผู้ส่งคำสั่ง)</h2>
{_paper_section(live_snap, store=store, live=True)}
{levels_table_html(store, settings)}
{_track_record_section(store)}

<h2>PAPER book — the daemon's training ground / พอร์ตจำลอง</h2>
{_paper_section(snap)}

<h2>Data freshness / ความสดของข้อมูล</h2>
<p class="sub">{" · ".join(f"{t.replace('.BK','')}: {d}" for t, d in sorted(freshness.items()))}</p>

<div class="note">Educational bookkeeping and simulation. Not investment advice.
Claude never executes real trades. / รายงานนี้เพื่อการติดตามและการเรียนรู้เท่านั้น
ไม่ใช่คำแนะนำการลงทุน Claude ไม่มีการส่งคำสั่งซื้อขายจริงในทุกกรณี</div>
</body></html>"""
