"""Convert the latest reports into artifact-ready pages at STABLE paths.

Artifacts wrap content in their own document skeleton, so we strip our
<!doctype>/<html>/<head>/<body> wrapper and emit: <title> + <style> + body
content. Stable paths => republishing updates the same URLs.

Usage:  .venv/bin/python scripts/publish_pages.py
Writes: reports/live/portfolio.html , reports/live/risk.html
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import PROJECT_ROOT  # noqa: E402

LIVE = PROJECT_ROOT / "reports" / "live"


def artifactify(src: Path, title: str) -> str:
    html = src.read_text(encoding="utf-8")
    style = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    body = re.search(r"<body>(.*?)</body>", html, re.S).group(1)
    return f"<title>{title}</title>\n<style>{style}</style>\n{body}"


def latest(pattern: str) -> Path:
    files = sorted((PROJECT_ROOT / "reports").glob(pattern))
    if not files:
        raise SystemExit(f"no report matching {pattern} — generate it first")
    return files[-1]


def main():
    LIVE.mkdir(parents=True, exist_ok=True)
    jobs = [
        (latest("portfolio_*.html"), "CLAUDE TRADE Portfolio", "portfolio.html"),
        (latest("risk_plan_*.html"), "CLAUDE TRADE Risk Deck", "risk.html"),
        (latest("research_*.html"), "CLAUDE TRADE Research Deck", "research.html"),
        (latest("performance_*.html"), "CLAUDE TRADE Performance", "performance.html"),
    ]
    for src, title, out_name in jobs:
        out = LIVE / out_name
        out.write_text(artifactify(src, title), encoding="utf-8")
        print(f"{src.name} -> {out}")


if __name__ == "__main__":
    main()
