"""Render the bilingual research deck from structured research results.

Usage:  .venv/bin/python scripts/research_deck.py <results.json>
        -> reports/research_YYYY-MM-DD.html
The JSON is a list of per-name research objects (see workflow schema):
dr, underlying, company, metrics{}, thesis_en, thesis_th, risks[], watch[],
next_earnings, sources[].
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import PROJECT_ROOT  # noqa: E402

CSS = """body{font-family:-apple-system,'Sukhumvit Set',sans-serif;margin:2rem auto;
max-width:880px;color:#1a1a2e;background:#fafafa;padding:0 1rem}
h1{font-size:1.4rem}h2{font-size:1.15rem;margin-top:2.4rem;border-top:2px solid #1a1a2e;
padding-top:1rem}h3{font-size:.95rem;margin:1rem 0 .3rem}
table{border-collapse:collapse;width:100%;font-size:.88rem;margin:.5rem 0}
th,td{padding:5px 9px;text-align:left;border-bottom:1px solid #ddd;vertical-align:top}
th{background:#1a1a2e;color:#fff}
.sub{color:#666;font-size:.85rem}
.th{background:#f0f4ff;border-left:3px solid #2a78d6;padding:.7rem .9rem;border-radius:0 6px 6px 0;
font-size:.92rem;margin:.5rem 0}
ul{margin:.3rem 0 .3rem 1.2rem;padding:0}li{margin:.25rem 0;font-size:.9rem}
.note{color:#666;font-size:.8rem;margin-top:2rem;border-top:1px solid #ddd;padding-top:.8rem}
a{color:#2a78d6;text-decoration:none;font-size:.8rem}"""

METRIC_LABELS = [
    ("trailingPE", "P/E (trailing) / พีอีย้อนหลัง"),
    ("forwardPE", "P/E (forward) / พีอีล่วงหน้า"),
    ("priceToSalesTrailing12Months", "P/S / ราคาต่อยอดขาย"),
    ("enterpriseToEbitda", "EV/EBITDA"),
    ("grossMargins", "Gross margin / กำไรขั้นต้น"),
    ("operatingMargins", "Operating margin / กำไรจากการดำเนินงาน"),
    ("revenueGrowth", "Revenue growth YoY / ยอดขายโต"),
    ("earningsGrowth", "Earnings growth / กำไรโต"),
    ("marketCap", "Market cap / มูลค่าบริษัท"),
    ("dividendYield", "Dividend yield / ปันผล"),
    ("expense_ratio", "Expense ratio / ค่าธรรมเนียมกองทุน"),
    ("index_pe", "Index P/E / พีอีดัชนี"),
    ("top_holdings", "Top holdings / หุ้นหลักในกอง"),
]


def fmt(key, v):
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        if key in ("grossMargins", "operatingMargins", "revenueGrowth",
                   "earningsGrowth", "dividendYield"):
            return f"{100 * v:.1f}%" if abs(v) < 5 else f"{v:.1f}%"
        if key == "marketCap":
            return f"${v / 1e9:,.0f}B" if v > 1e9 else f"{v:,.0f}"
        return f"{v:,.1f}"
    return str(v)


def section(r):
    metrics = r.get("metrics") or {}
    rows = "".join(
        f"<tr><td>{label}</td><td>{fmt(k, metrics[k])}</td></tr>"
        for k, label in METRIC_LABELS if k in metrics and metrics[k] is not None
    )
    risks = "".join(f"<li>{x}</li>" for x in r.get("risks", []))
    watch = "".join(f"<li>{x}</li>" for x in r.get("watch", []))
    srcs = " · ".join(f'<a href="{u}">source</a>' for u in (r.get("sources") or [])[:4])
    return f"""
<h2>{r['dr']} — {r['company']} ({r['underlying']})</h2>
<p class="sub">Next earnings / งบครั้งถัดไป: {r.get('next_earnings', 'unknown')}</p>
<table><tr><th>Metric / ตัวชี้วัด</th><th>Value / ค่า</th></tr>{rows}</table>
<h3>Why the daemon holds it / ทำไมถึงถือ</h3>
<p>{r['thesis_en']}</p>
<div class="th">🇹🇭 {r['thesis_th']}</div>
<h3>Risks / ความเสี่ยง</h3><ul>{risks}</ul>
<h3>What would break the thesis / อะไรจะทำให้เหตุผลนี้พัง</h3><ul>{watch}</ul>
{srcs}"""


def main():
    results = json.loads(Path(sys.argv[1]).read_text())
    if isinstance(results, dict):   # task-output wrapper {"summary":..., "result": [...]}
        results = results["result"]
    order = {"TDEX": 0}
    results.sort(key=lambda r: (order.get(r["dr"], 1), r["dr"]))
    body = "".join(section(r) for r in results)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CLAUDE TRADE Research Deck</title><style>{CSS}</style></head><body>
<h1>🔬 Research Deck — LIVE sleeve / บทวิเคราะห์หุ้นในพอร์ต</h1>
<p class="sub">Generated {date.today().isoformat()} · Honest context on each holding.
Important: the daemon PICKED these names on price momentum, not fundamentals — this
research is the cross-check, and the exit plan (stops, trend, rotation) is what manages
being wrong. / เดมอนเลือกหุ้นจากโมเมนตัมราคา ไม่ใช่ปัจจัยพื้นฐาน —
บทวิเคราะห์นี้คือการตรวจทาน และแผนการขายคือกลไกจัดการเมื่อคิดผิด</p>
{body}
<div class="note">Educational research, not investment advice. Figures from Yahoo Finance
and cited sources; may lag reality. / เพื่อการศึกษา ไม่ใช่คำแนะนำการลงทุน</div>
</body></html>"""
    out = PROJECT_ROOT / "reports" / f"research_{date.today().isoformat()}.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
