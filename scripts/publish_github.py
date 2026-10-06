"""Publish the three generated pages to GitHub Pages (public, noindex).

The site repo (site/, git-ignored from the main project) holds ONLY rendered
HTML + robots.txt. Never code, never the database, never config.

Usage:  .venv/bin/python scripts/publish_github.py
"""
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import load_settings, PROJECT_ROOT  # noqa: E402

SITE = PROJECT_ROOT / "site"
NOINDEX = '<meta name="robots" content="noindex, nofollow, noarchive">'
PAGES = [("portfolio_*.html", "portfolio.html", "📊 Portfolio / พอร์ต"),
         ("risk_plan_*.html", "risk.html", "🎯 Risk & Exit Plan / แผนความเสี่ยง"),
         ("research_*.html", "research.html", "🔬 Research / บทวิเคราะห์"),
         ("performance_*.html", "performance.html", "📈 Performance / ผลงาน")]


def latest(pattern):
    files = sorted((PROJECT_ROOT / "reports").glob(pattern))
    return files[-1] if files else None


def harden(html: str) -> str:
    """Inject noindex right after the charset meta; idempotent."""
    if NOINDEX in html:
        return html
    return html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n' + NOINDEX, 1)


def build_site():
    SITE.mkdir(exist_ok=True)
    links = ""
    for pattern, out_name, label in PAGES:
        src = latest(pattern)
        if src is None:
            continue
        (SITE / out_name).write_text(harden(src.read_text(encoding="utf-8")), encoding="utf-8")
        links += f'<li><a href="{out_name}">{label}</a> <span class="sub">({src.stem.split("_")[-1]})</span></li>'
    (SITE / "index.html").write_text(f"""<!doctype html><html><head><meta charset="utf-8">
{NOINDEX}<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CLAUDE TRADE</title>
<style>body{{font-family:-apple-system,'Sukhumvit Set',sans-serif;max-width:640px;margin:3rem auto;
padding:0 1rem;color:#1a1a2e;background:#fafafa}}li{{margin:.6rem 0;font-size:1.05rem}}
.sub{{color:#666;font-size:.85rem}}a{{color:#2a78d6}}</style></head><body>
<h1>CLAUDE TRADE</h1><p class="sub">Updated {date.today().isoformat()} · unlisted page — please don't share the link onward</p>
<ul>{links}</ul>
<p class="sub">Educational bookkeeping and simulation. Not investment advice.</p></body></html>""",
                                     encoding="utf-8")
    (SITE / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    (SITE / ".nojekyll").write_text("")


def push():
    repo = load_settings()["github_pages"]["repo"]
    run = lambda *a: subprocess.run(a, cwd=SITE, capture_output=True, text=True)
    if not (SITE / ".git").exists():
        run("git", "init", "-b", "main")
        run("git", "remote", "add", "origin", f"https://github.com/{repo}.git")
    run("git", "add", "-A")
    c = run("git", "commit", "-q", "-m", f"pages {date.today().isoformat()}")
    if "nothing to commit" in (c.stdout + c.stderr):
        print("site unchanged — nothing pushed")
        return
    p = run("git", "push", "-u", "origin", "main")
    print("pushed" if p.returncode == 0 else f"PUSH FAILED: {p.stderr.strip()[-300:]}")


if __name__ == "__main__":
    build_site()
    import subprocess
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "build_dashboard.py")], check=True)
    push()
    print(load_settings()["github_pages"]["url"])
