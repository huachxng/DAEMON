"""One-page tabbed site: Overview + Portfolio + Risk + Research + Performance.

Design: "The Private Ledger" — vault-green shell, porcelain paper, antique gold,
Cormorant Garamond display. The four report HTMLs are imported as tab panels and
restyled by one unified skin (they share the same class vocabulary).

Usage:  .venv/bin/python scripts/build_dashboard.py  ->  site/index.html
"""
import math
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, PROJECT_ROOT
from src.datafeed.store import Store
from src.digest.levels import levels_rows
from src.paperbot.bot import paper_snapshot

DONUT = ["#ac8b50", "#2f5d48", "#7d9c8f", "#c9b489", "#4a6c5d", "#96876a"]
CASH = "#cfc9ba"
NOINDEX = '<meta name="robots" content="noindex, nofollow, noarchive">'

TABS = [  # (id, label_en, label_th, source glob or None for overview)
    ("overview", "Overview", "ภาพรวม", None),
    ("portfolio", "Portfolio", "พอร์ต", "portfolio_*.html"),
    ("risk", "Risk & Exits", "ความเสี่ยง", "risk_plan_*.html"),
    ("research", "Research", "บทวิเคราะห์", "research_*.html"),
    ("performance", "Performance", "ผลงาน", "performance_*.html"),
]


def panel_from_report(pattern):
    files = sorted((PROJECT_ROOT / "reports").glob(pattern))
    if not files:
        return "<p class='sub'>—</p>"
    html = files[-1].read_text(encoding="utf-8")
    body = re.search(r"<body>(.*?)</body>", html, re.S).group(1)
    body = re.sub(r"<style>.*?</style>", "", body, flags=re.S)
    body = re.sub(r"<title>.*?</title>", "", body, flags=re.S)
    return body


def donut(slices):
    total = sum(v for _, v, _ in slices) or 1
    r, c, w = 64, 82, 24
    circ = 2 * math.pi * r
    off, arcs = 0.25 * circ, ""
    for label, v, color in slices:
        frac = v / total
        arcs += (f'<circle r="{r}" cx="{c}" cy="{c}" fill="none" stroke="{color}" '
                 f'stroke-width="{w}" stroke-dasharray="{max(frac*circ-2.5,0.1):.1f} '
                 f'{circ-max(frac*circ-2.5,0.1):.1f}" stroke-dashoffset="{-off:.1f}" '
                 f'transform="rotate(-90 {c} {c})"/>')
        off += frac * circ
    legend = "".join(
        f'<div class="lg"><span class="dot" style="background:{cl}"></span>'
        f'{l}<span class="lgv">{100*v/total:.0f}%</span></div>'
        for l, v, cl in slices)
    return (f'<div class="donutwrap"><svg width="164" height="164" viewBox="0 0 164 164">{arcs}</svg>'
            f'<div class="legend">{legend}</div></div>')


def main():
    settings = load_settings()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    snap = paper_snapshot(store, settings, book="live")
    hist = store.read_equity_history("live")
    day_chg = (snap["equity"] - hist[-2]["equity"]) if len(hist) >= 2 else 0.0
    pct = 100 * (snap["equity"] / 200_000 - 1)
    prog = max(0.0, min(1.0, (snap["equity"] - 200_000) / 20_000))

    slices = [(r["ticker"].replace(".BK", ""), r["value"], DONUT[i % len(DONUT)])
              for i, r in enumerate(sorted(snap["rows"], key=lambda x: -x["value"]))]
    slices.append(("Cash", snap["cash"], CASH))

    perf = sorted((PROJECT_ROOT / "reports").glob("performance_*.html"))
    chart = ""
    if perf:
        m = re.search(r'base64,([^"]+)"', perf[-1].read_text(encoding="utf-8"))
        if m:
            chart = f'<img src="data:image/png;base64,{m.group(1)}" alt="equity curve">'

    lv = "".join(f"<tr><td>{r['ticker']}</td><td>{r['qty']:,.0f}</td>"
                 f"<td>{r['cost']:.2f}</td><td class='gold'>{r['stop']:.2f}</td></tr>"
                 for r in levels_rows(store, settings))
    ev = "".join(f"<tr><td>{e['ts'][:10]}</td><td>{e['event'].replace('_',' ')}</td>"
                 f"<td>{e['side']} {e['qty']:g} {e['ticker'].replace('.BK','')}</td></tr>"
                 for e in reversed(store.read_order_events("live")[-8:]))

    chip = {"normal": ("chip-ok", "NORMAL"), "halt_buys": ("chip-warn", "DE-RISK"),
            "liquidate": ("chip-bad", "LIQUIDATED")}[snap["state"]]
    chg_cls = "pos" if day_chg >= 0 else "neg"

    overview = f"""
<section class="hero">
 <div class="eyebrow">LIVE SLEEVE · อัปเดต {date.today().isoformat()}</div>
 <div class="figure">฿{snap['equity']:,.0f}<span class="chip {chip[0]}">{chip[1]}</span></div>
 <div class="heroline"><span class="{chg_cls}">{day_chg:+,.0f} today</span>
 <span class="dim">{pct:+.1f}% from ฿200,000 · target +10–30% by 13 Oct</span></div>
 <div class="bar"><i style="width:{100*prog:.0f}%"></i></div>
 <div class="dim small">progress to +10% (฿220,000): {100*prog:.0f}%</div>
</section>
<div class="cards">
 <div class="card r1"><h2>Allocation · สัดส่วน</h2>{donut(slices)}</div>
 <div class="card r2"><h2>Equity curve · เส้นทางพอร์ต</h2>{chart}</div>
 <div class="card r3"><h2>Cut-loss levels · จุดตัดขาดทุน</h2>
  <table><tr><th>Name</th><th>Qty</th><th>Avg cost</th><th>Cut-loss ฿</th></tr>{lv}</table></div>
 <div class="card r4"><h2>Latest orders · คำสั่งล่าสุด</h2>
  <table><tr><th>Date</th><th>Event</th><th>Order</th></tr>{ev}</table></div>
</div>"""

    nav = "".join(f'<a href="#{tid}" data-tab="{tid}">{en}<span class="th-lbl">{th}</span></a>'
                  for tid, en, th, _ in TABS)
    panels = f'<div class="panel" id="p-overview">{overview}</div>' + "".join(
        f'<div class="panel" id="p-{tid}" hidden>{panel_from_report(g)}</div>'
        for tid, _, _, g in TABS if g)

    tab_ids = [t[0] for t in TABS]
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
{NOINDEX}<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CLAUDE TRADE</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--shell:#10201a;--shell-ink:#e9e4d8;--paper:#f4f1e9;--card:#fffefa;--ink:#1a1c19;
--muted:#71736a;--line:#e0dacb;--gold:#ac8b50;--gold-soft:#d8c9a5;--pos:#1e7a46;--neg:#ad3a2d}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
font:15px/1.55 -apple-system,'Sukhumvit Set',BlinkMacSystemFont,sans-serif;
font-variant-numeric:tabular-nums}}
.serif{{font-family:'Cormorant Garamond','Sukhumvit Set',Georgia,serif}}
header{{background:var(--shell);color:var(--shell-ink);position:sticky;top:0;z-index:9;
border-bottom:1px solid rgba(217,201,165,.25)}}
.bar-in{{max-width:960px;margin:0 auto;padding:.9rem 1.2rem;display:flex;align-items:center;
justify-content:space-between;gap:1rem;flex-wrap:wrap}}
.wordmark{{font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;font-size:1.35rem;
letter-spacing:.14em}}.wordmark b{{color:var(--gold-soft);font-weight:600}}
nav{{display:flex;gap:.2rem;overflow-x:auto}}
nav a{{color:var(--shell-ink);text-decoration:none;font-size:.72rem;letter-spacing:.14em;
text-transform:uppercase;padding:.5rem .8rem;border-bottom:2px solid transparent;
white-space:nowrap;opacity:.75;transition:all .2s}}
nav a .th-lbl{{display:block;font-size:.6rem;letter-spacing:.05em;opacity:.6;text-transform:none}}
nav a:hover{{opacity:1}}nav a.on{{opacity:1;border-bottom-color:var(--gold)}}
main{{max-width:960px;margin:0 auto;padding:1.6rem 1.2rem 3rem}}
.hero{{padding:1.6rem 0 1rem}}
.eyebrow{{font-size:.68rem;letter-spacing:.22em;text-transform:uppercase;color:var(--muted)}}
.figure{{font-family:'Cormorant Garamond',Georgia,serif;font-weight:700;font-size:3.4rem;
line-height:1.1;margin:.2rem 0;display:flex;align-items:center;gap:1rem;flex-wrap:wrap}}
.chip{{font:700 .62rem/1 -apple-system,sans-serif;letter-spacing:.16em;padding:.45em .9em;
border-radius:999px;color:#fff}}
.chip-ok{{background:var(--pos)}}.chip-warn{{background:#b98a1d}}.chip-bad{{background:var(--neg)}}
.heroline{{display:flex;gap:1.2rem;flex-wrap:wrap;font-size:.95rem}}
.dim{{color:var(--muted)}}.small{{font-size:.8rem}}
.bar{{height:6px;background:var(--line);border-radius:999px;margin:.9rem 0 .3rem;overflow:hidden}}
.bar i{{display:block;height:100%;background:linear-gradient(90deg,var(--gold),var(--gold-soft))}}
.cards{{display:grid;grid-template-columns:1fr 1fr;gap:1.1rem;margin-top:1.2rem}}
@media(max-width:760px){{.cards{{grid-template-columns:1fr}}}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:1.1rem 1.2rem;box-shadow:0 1px 2px rgba(26,28,25,.04)}}
.card.r2,.card.r3,.card.r4{{grid-column:1/-1}}
.donutwrap{{display:flex;gap:1.4rem;align-items:center;flex-wrap:wrap}}
.legend{{display:flex;flex-direction:column;gap:5px}}
.lg{{display:flex;align-items:center;gap:8px;font-size:.85rem}}
.dot{{width:10px;height:10px;border-radius:2px;display:inline-block}}
.lgv{{color:var(--muted);margin-left:.3rem}}
h1{{font-family:'Cormorant Garamond','Sukhumvit Set',Georgia,serif;font-size:1.7rem;
font-weight:600;margin:1.6rem 0 .4rem}}
h2{{font-family:'Cormorant Garamond','Sukhumvit Set',Georgia,serif;font-size:1.25rem;
font-weight:600;margin:1.8rem 0 .6rem;padding-top:1rem;border-top:1px solid var(--line)}}
.card h2{{border-top:none;margin:.1rem 0 .8rem;padding-top:0}}
h3{{font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);
margin:1.2rem 0 .4rem}}
table{{border-collapse:collapse;width:100%;font-size:.88rem;margin:.5rem 0}}
th{{background:transparent;color:var(--muted);font-size:.68rem;letter-spacing:.14em;
text-transform:uppercase;font-weight:600;text-align:right;padding:6px 10px;
border-bottom:1.5px solid var(--gold-soft)}}
td{{padding:7px 10px;text-align:right;border-bottom:1px solid var(--line)}}
td:first-child,th:first-child{{text-align:left}}
tr.total td{{font-weight:700;border-top:1.5px solid var(--ink)}}
.pos{{color:var(--pos)}}.neg{{color:var(--neg)}}.gold{{color:var(--gold);font-weight:700}}
.sub{{color:var(--muted);font-size:.85rem}}
.banner{{background:#f7efe0;border:1px solid var(--gold-soft);border-left:3px solid var(--gold);
border-radius:6px;padding:10px 14px;margin:.8rem 0;font-size:.88rem}}
.th{{background:#eef0e9;border-left:3px solid #2f5d48;padding:.7rem .9rem;
border-radius:0 6px 6px 0;font-size:.9rem;margin:.5rem 0}}
img{{max-width:100%;border-radius:8px}}
ul{{margin:.3rem 0 .3rem 1.2rem;padding:0}}li{{margin:.3rem 0;font-size:.9rem}}
a{{color:#2f5d48}}
.note{{color:var(--muted);font-size:.78rem;margin-top:2.4rem;border-top:1px solid var(--line);
padding-top:.9rem}}
.panel>h1:first-of-type{{display:none}}
footer{{background:var(--shell);color:rgba(233,228,216,.65);font-size:.75rem;
text-align:center;padding:1.4rem 1rem;letter-spacing:.04em}}
footer b{{color:var(--gold-soft);font-weight:600}}
@media(prefers-reduced-motion:no-preference){{
.hero,.card,.panel{{animation:rise .5s ease both}}
.card:nth-child(2){{animation-delay:.06s}}.card:nth-child(3){{animation-delay:.12s}}
.card:nth-child(4){{animation-delay:.18s}}
@keyframes rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}}}
</style></head><body>
<header><div class="bar-in">
<div class="wordmark">CLAUDE <b>TRADE</b></div>
<nav id="nav">{nav}</nav>
</div></header>
<main>{panels}</main>
<footer>Educational bookkeeping &amp; simulation — <b>not investment advice</b> ·
Claude never executes trades · เพื่อการเรียนรู้ ไม่ใช่คำแนะนำการลงทุน</footer>
<script>
(function(){{
var tabs={tab_ids};
function show(id){{if(tabs.indexOf(id)<0)id='overview';
tabs.forEach(function(t){{document.getElementById('p-'+t).hidden=(t!==id);}});
document.querySelectorAll('#nav a').forEach(function(a){{
a.classList.toggle('on',a.dataset.tab===id);}});
window.scrollTo({{top:0}});}}
window.addEventListener('hashchange',function(){{show(location.hash.slice(1));}});
show(location.hash.slice(1)||'overview');
}})();
</script></body></html>"""
    out = PROJECT_ROOT / "site" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out, f"({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
