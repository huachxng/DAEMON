"""Performance pack: equity curve vs target paths, attribution, grade backlog.

Usage:  .venv/bin/python scripts/performance.py -> reports/performance_<date>.html
"""
import base64
import io
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.config import load_settings, PROJECT_ROOT
from src.datafeed.store import Store
from src.paperbot.bot import paper_snapshot, _price_thb
from src.risk.performance import attribution

BLUE, ORANGE, AQUA, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#e87ba4"
CRITICAL, SERIOUS, WARN = "#d03b3b", "#ec835a", "#fab219"
INK, MUTED, GRID = "#374151", "#6b7280", "#e5e7eb"
START, TARGET_DATE = "2026-08-14", "2026-10-13"


def fmt(x, dp=0):
    return f"{x:,.{dp}f}"


def curve_chart(store):
    hist = store.read_equity_history("live")
    eq = pd.Series([h["equity"] for h in hist],
                   index=pd.to_datetime([h["date"] for h in hist]))
    start, end = pd.Timestamp(START), pd.Timestamp(TARGET_DATE)

    fig, ax = plt.subplots(figsize=(9.5, 4.8), dpi=140)
    for target, c, lbl in ((260_000, "#cde2fb", "+30% path"), (220_000, "#9ec5f4", "+10% path")):
        ax.plot([start, end], [200_000, target], color=c, lw=2, ls="--")
        ax.annotate(f" {lbl}", xy=(end, target), fontsize=8.5, color=BLUE, va="center")
    for level, c, lbl in ((160_000, WARN, "de-risk 160k"), (155_000, SERIOUS, "liquidate 155k"),
                          (150_000, CRITICAL, "FLOOR 150k")):
        ax.axhline(level, color=c, lw=1.2, ls=":" if level > 150_000 else "--")
        ax.annotate(f" {lbl}", xy=(start, level), fontsize=8, color=c, va="bottom")

    for sym, c, lbl in (("TDEX.BK", AQUA, "TDEX (indexed)"), ("^GSPC", MAGENTA, "S&P 500 (indexed)")):
        df = store.read_prices(sym)
        s = pd.Series(df["close"].values, index=pd.to_datetime(df["date"]))
        s = s[s.index >= start]
        if len(s):
            ax.plot(s.index, 200_000 * s / s.iloc[0], color=c, lw=1.6, alpha=0.85, label=lbl)

    ax.plot(eq.index, eq.values, color=BLUE, lw=2.6, label="LIVE sleeve", zorder=5)
    if len(eq):
        ax.plot(eq.index[-1], eq.iloc[-1], "o", color=BLUE, ms=7, zorder=6)
        ax.annotate(f" ฿{eq.iloc[-1]:,.0f}", xy=(eq.index[-1], eq.iloc[-1]),
                    fontsize=9, color=INK, fontweight="bold", va="bottom")
    ax.set_xlim(start, end)
    ax.set_ylim(145_000, 265_000)
    ax.legend(loc="upper left", fontsize=8.5, frameon=False)
    ax.grid(color=GRID, lw=0.6)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.set_title("Equity vs target paths — ฿200,000 start, day 60 = Oct 13",
                 fontsize=11, color=INK, loc="left")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def main():
    settings = load_settings()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    snap = paper_snapshot(store, settings, book="live")
    trades = store.read_trades("live")

    prices = {}
    for t in {tr.ticker for tr in trades}:
        _, px = _price_thb(store, t, "close", snap["fx"])
        prices[t] = px or 0.0
    rows = attribution(trades, prices)
    fees_total = sum(r["fees"] for r in rows)
    pl_total = sum(r["realized"] + r["unrealized"] for r in rows)

    att = "".join(
        f"<tr><td>{r['ticker'].replace('.BK','')}</td><td>{fmt(r['qty'])}</td>"
        f"<td class='{ 'pos' if r['realized']>=0 else 'neg'}'>{fmt(r['realized'],2)}</td>"
        f"<td class='{ 'pos' if r['unrealized']>=0 else 'neg'}'>{fmt(r['unrealized'],2)}</td>"
        f"<td>{fmt(r['fees'],2)}</td>"
        f"<td class='{ 'pos' if r['realized']+r['unrealized']>=0 else 'neg'}'><b>{fmt(r['realized']+r['unrealized'],2)}</b></td></tr>"
        for r in rows)

    ungraded_all = [j for j in store.read_journal_tail(60)
                    if j["book"] == "live" and not j["grade"]]
    # Collapse identical repeated actions (daily reminders) into one line — one
    # grade covers them all (applied to every identical row on reply).
    seen, ungraded = {}, []
    for j in reversed(ungraded_all):          # oldest first
        if j["action"] in seen:
            seen[j["action"]]["n"] += 1
        else:
            seen[j["action"]] = {**j, "n": 1}
            ungraded.append(seen[j["action"]])
    ungraded.reverse()
    backlog = "".join(
        f"<li><b>#{j['id']}</b> {j['ts'][:10]} — {j['action'][:80]}"
        + (f" <span class='sub'>(×{j['n']} identical days — one grade covers all)</span>" if j["n"] > 1 else "")
        + "</li>"
        for j in ungraded)

    img = curve_chart(store)
    pct = 100 * (snap["equity"] / 200_000 - 1)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CLAUDE TRADE Performance</title><style>
body{{font-family:-apple-system,'Sukhumvit Set',sans-serif;margin:2rem auto;max-width:900px;
color:#1a1a2e;background:#fafafa;padding:0 1rem}}h1{{font-size:1.4rem}}
h2{{font-size:1.1rem;margin-top:2rem}}table{{border-collapse:collapse;width:100%;font-size:.9rem}}
th,td{{padding:5px 9px;text-align:right;border-bottom:1px solid #ddd}}
th{{background:#1a1a2e;color:#fff}}td:first-child,th:first-child{{text-align:left}}
.pos{{color:#0a7a2f}}.neg{{color:#c0392b}}.sub{{color:#666;font-size:.85rem}}
ul{{margin:.3rem 0 .3rem 1.2rem}}li{{margin:.3rem 0;font-size:.9rem}}
.note{{color:#666;font-size:.8rem;margin-top:2rem;border-top:1px solid #ddd;padding-top:.8rem}}</style></head><body>
<h1>📈 Performance — LIVE sleeve / ผลงานพอร์ตเดมอน</h1>
<p class="sub">Generated {date.today().isoformat()} · Equity <b>฿{fmt(snap['equity'])}</b>
({pct:+.1f}% from ฿200,000 start) · target +10–30% by 2026-10-13 / เป้าหมาย +10–30% ภายใน 13 ต.ค.</p>
<img src="data:image/png;base64,{img}" style="max-width:100%">
<h2>Attribution / ที่มาของกำไร-ขาดทุน</h2>
<table><tr><th>Name</th><th>Qty</th><th>Realized ฿</th><th>Unrealized ฿</th><th>Fees ฿</th><th>Total ฿</th></tr>
{att}
<tr class="total"><td><b>Total</b></td><td></td><td></td><td></td><td><b>{fmt(fees_total,2)}</b></td>
<td class='{ "pos" if pl_total>=0 else "neg"}'><b>{fmt(pl_total,2)}</b></td></tr></table>
<p class="sub">Identity check: sum of totals = equity − 200,000 = ฿{fmt(snap['equity']-200_000,2)}
(fees are already inside realized/unrealized — the Fees column shows drag, not an extra deduction) /
ค่าธรรมเนียมรวมอยู่ในตัวเลขกำไร-ขาดทุนแล้ว คอลัมน์ Fees แสดงภาระต้นทุนเฉยๆ</p>
<h2>Decisions awaiting your grade / คำตัดสินที่รอเกรด ({len(ungraded)})</h2>
<p class="sub">Reply in the [CLAUDE TRADE] email thread: <code>grade #id A–F [comment]</code></p>
<ul>{backlog or "<li>none 🎉</li>"}</ul>
<div class="note">Educational bookkeeping and simulation. Not investment advice. /
เพื่อการติดตามและการเรียนรู้ ไม่ใช่คำแนะนำการลงทุน</div></body></html>"""
    out = PROJECT_ROOT / "reports" / f"performance_{date.today().isoformat()}.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
