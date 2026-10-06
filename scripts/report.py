"""Generate today's portfolio report.

Usage:  .venv/bin/python scripts/report.py  ->  reports/portfolio_YYYY-MM-DD.html
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, PROJECT_ROOT
from src.datafeed.store import Store
from src.digest.report import build_report


def main():
    settings = load_settings()
    store = Store(PROJECT_ROOT / settings["data"]["db_path"])
    html = build_report(store, settings)
    out = PROJECT_ROOT / "reports" / f"portfolio_{date.today().isoformat()}.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
