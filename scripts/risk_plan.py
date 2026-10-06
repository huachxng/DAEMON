"""Per-position risk plan: scenario cones, cut-loss levels, exit rules — as charts.

Usage:  .venv/bin/python scripts/risk_plan.py  ->  reports/risk_plan_YYYY-MM-DD.html

Scenario cones are RANGES implied by each name's own last-year volatility
(zero-drift lognormal), not predictions. Charts follow the dataviz palette.
"""
import base64
import io
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import load_settings, load_universe, PROJECT_ROOT
from src.datafeed.store import Store
from src.digest.levels import levels_table_html, working_limits
from src.paperbot.bot import paper_snapshot
from src.risk.exits import HARD_STOP_FRAC

# dataviz validated palette
BLUE, ORANGE = "#2a78d6", "#eb6834"
CONE_1, CONE_2 = "#9ec5f4", "#cde2fb"
SERIOUS, CRITICAL = "#ec835a", "#d03b3b"
INK, MUTED, GRID = "#374151", "#6b7280", "#e5e7eb"

HORIZON = 63  # trading days ~ 3 months


def series(store, ticker, n=None):
    s = store.read_prices(ticker)
    s = s[s["close"].notna()]
    out = pd.Series(s["close"].values, index=pd.to_datetime(s["date"]))
    return out.tail(n) if n else out


def chart(name, px, sma, stop_level, trend_level, entry_note):
    """One position chart: 18mo price, SMA200, 3mo cone, exit lines. -> base64 png"""
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=140)
    hist = px.tail(378)
    ax.plot(hist.index, hist.values, color=BLUE, lw=2, label=name.split(" ")[0])
    if sma is not None:
        ax.plot(hist.index, sma.reindex(hist.index).values, color=ORANGE, lw=2,
                label="SMA200")

    # forward cone from last close, sigma from last 252d log returns, zero drift
    rets = np.log(px / px.shift(1)).dropna().tail(252)
    sig = float(rets.std())
    last, t = float(px.iloc[-1]), np.arange(1, HORIZON + 1)
    fdates = pd.bdate_range(px.index[-1], periods=HORIZON + 1)[1:]
    for z, c in ((2, CONE_2), (1, CONE_1)):
        ax.fill_between(fdates, last * np.exp(-z * sig * np.sqrt(t)),
                        last * np.exp(z * sig * np.sqrt(t)), color=c,
                        lw=0, zorder=1)
    ax.plot(fdates, np.full(HORIZON, last), color=BLUE, lw=1, ls=":", zorder=2)

    span_x = hist.index[0]
    for level, color, label in ((trend_level, SERIOUS, "TREND EXIT (SMA200)"),
                                (stop_level, CRITICAL, f"HARD STOP −{100*(1-HARD_STOP_FRAC):.0f}%")):
        if level is None:
            continue
        ax.axhline(level, color=color, lw=1.6, ls="--", zorder=3)
        ax.annotate(f" {label}  {level:,.2f}", xy=(span_x, level), fontsize=8.5,
                    color=color, va="bottom", fontweight="bold")

    ax.set_title(f"{name} — {entry_note}", fontsize=11, color=INK, loc="left")
    ax.legend(loc="upper left", fontsize=8.5, frameon=False, ncols=2)
    ax.grid(color=GRID, lw=0.6)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    for s_ in ("left", "bottom"):
        ax.spines[s_].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def scenario_rows(dr_price, qty, sig):
    rows = ""
    for z, label_en, label_th in ((-2, "Crash (−2σ)", "วิกฤต"), (-1, "Weak (−1σ)", "อ่อนแรง"),
                                  (0, "Flat", "ทรงตัว"), (1, "Good (+1σ)", "ดี"),
                                  (2, "Strong (+2σ)", "แรง")):
        mult = math.exp(z * sig * math.sqrt(HORIZON))
        p = dr_price * mult
        pl = qty * (p - dr_price)
        cls = "pos" if pl >= 0 else "neg"
        rows += (f"<tr><td>{label_en} / {label_th}</td><td>{100*(mult-1):+.1f}%</td>"
                 f"<td>{p:,.2f}</td><td class='{cls}'>{pl:+,.0f}</td></tr>")
    return rows


def main():
    settings, uni = load_settings(), load_universe()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    snap = paper_snapshot(store, settings, book="live")
    held = {r["ticker"]: r for r in snap["rows"]}
    u_of = {p["dr"]: p["underlying"] for p in uni["dr_map"]}

    # positions + working tickets (planned cost from the working limit order)
    plan = []
    for t, r in held.items():
        cost_pu = (r["value"] - r["unrealized"]) / r["qty"]
        plan.append((t, r["qty"], cost_pu, "HELD"))
    for o in snap["pending"]:
        if o["side"] != "BUY":
            continue
        # unheld tickets always get a card; held names only when an order is working
        wl = working_limits(store)
        if o["ticker"] in wl or o["ticker"] not in held:
            plan.append((o["ticker"], o["qty"], wl.get(o["ticker"]), "WORKING ORDER"))

    sections = ""
    for ticker, qty, cost_pu, status in sorted(plan):
        short = ticker.replace(".BK", "")
        u = u_of.get(ticker)
        chart_px = series(store, u) if u else series(store, ticker)
        sma = chart_px.rolling(200).mean() if len(chart_px) >= 200 else None
        trend_level = float(sma.iloc[-1]) if sma is not None else None

        dr_px = series(store, ticker)
        dr_last = float(dr_px.iloc[-1])
        stop_dr = cost_pu * HARD_STOP_FRAC if cost_pu else None
        # map the DR stop into underlying scale for the chart line
        stop_chart = (float(chart_px.iloc[-1]) * stop_dr / dr_last) if (u and stop_dr) else stop_dr

        rets = np.log(dr_px / dr_px.shift(1)).dropna().tail(252)
        sig = float(rets.std()) if len(rets) > 20 else \
            float(np.log(chart_px / chart_px.shift(1)).dropna().tail(252).std())

        entry_note = (f"{status}: {qty:g} @ ฿{cost_pu:,.2f}" if cost_pu
                      else f"{status}: {qty:g}")
        img = chart(f"{short}" + (f"  (underlying {u})" if u else ""),
                    chart_px, sma, stop_chart, trend_level, entry_note)

        dist_stop = 100 * (stop_dr / dr_last - 1) if stop_dr else None
        trend_dist = (100 * (float(chart_px.iloc[-1]) / trend_level - 1)
                      if trend_level else None)
        facts = f"""
<table>
<tr><th>Exit layer / ชั้นการขาย</th><th>Trigger / เงื่อนไข</th><th>Level now / ระดับปัจจุบัน</th></tr>
<tr><td>1. Hard stop / จุดตัดขาดทุน</td>
<td>DR closes ≤ −{100*(1-HARD_STOP_FRAC):.0f}% from cost → SELL ticket next run</td>
<td>{f"฿{stop_dr:,.2f} ({dist_stop:+.1f}% from last)" if stop_dr else "set on fill"}</td></tr>
<tr><td>2. Trend break / หลุดแนวโน้ม</td>
<td>{'Underlying closes below its 200-day SMA → SELL ticket' if u else 'n/a (no underlying — core ETF)'}</td>
<td>{f"{trend_level:,.2f} (price {trend_dist:+.1f}% above)" if trend_level else "—"}</td></tr>
<tr><td>3. Momentum rotation / หมุนออกตามโมเมนตัม</td>
<td>Drops out of top-5 at the quarterly re-pick</td><td>next re-pick ≈ 2026-11-02</td></tr>
<tr><td>4. Book breaker / เบรกเกอร์ทั้งพอร์ต</td>
<td>Sleeve equity ≤ ฿160k halt buys · ≤ ฿155k liquidate ALL</td>
<td>equity ฿{snap['equity']:,.0f}</td></tr>
</table>
<p class="sub">3-month scenario ranges from this name's own 1-year volatility
(σ_daily = {100*sig:.1f}%) — ranges, not predictions / ช่วงที่เป็นไปได้จากความผันผวนจริง
ไม่ใช่คำทำนาย · ~68% of history lands inside ±1σ</p>
<table>
<tr><th>Scenario / สถานการณ์</th><th>Move</th><th>DR price ฿</th><th>Position P&L ฿</th></tr>
{scenario_rows(dr_last, qty, sig)}
</table>"""
        sections += (f'<h2>{short} — {status}</h2>'
                     f'<img src="data:image/png;base64,{img}" style="max-width:100%">'
                     + facts)

    css = """body{font-family:-apple-system,'Sukhumvit Set',sans-serif;margin:2rem auto;
max-width:900px;color:#1a1a2e;background:#fafafa;padding:0 1rem}
h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:2.2rem;border-top:2px solid #1a1a2e;padding-top:1rem}
table{border-collapse:collapse;width:100%;font-size:.9rem;margin:.6rem 0}
th,td{padding:5px 9px;text-align:left;border-bottom:1px solid #ddd}
th{background:#1a1a2e;color:#fff}.pos{color:#0a7a2f}.neg{color:#c0392b}
.sub{color:#666;font-size:.85rem}
.note{color:#666;font-size:.8rem;margin-top:2rem;border-top:1px solid #ddd;padding-top:.8rem}"""

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CLAUDE TRADE — Risk & Exit Plan</title><style>{css}</style></head><body>
<h1>🎯 Risk & Exit Plan — LIVE sleeve / แผนความเสี่ยงและจุดขาย</h1>
<p class="sub">Generated {date.today().isoformat()} · Every position has four coded exit
layers, checked daily by the daemon. Cones show 3-month ranges implied by each name's
own historical volatility (zero drift) — they are honest ranges, not forecasts. /
ทุกตำแหน่งมีชั้นการขาย 4 ชั้น ตรวจอัตโนมัติทุกวัน กรวยแสดงช่วงราคาที่เป็นไปได้ 3 เดือน
จากความผันผวนในอดีต ไม่ใช่การพยากรณ์</p>
{levels_table_html(store, settings)}
{sections}
<div class="note">Educational simulation and bookkeeping. Not investment advice.
Claude never executes trades — every SELL is a ticket the user chooses to execute. /
ไม่ใช่คำแนะนำการลงทุน ทุกคำสั่งขายเป็นตั๋วที่ผู้ใช้ตัดสินใจส่งเอง</div>
</body></html>"""
    out = PROJECT_ROOT / "reports" / f"risk_plan_{date.today().isoformat()}.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
