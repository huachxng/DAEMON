"""Publish the SOURCE to the public GitHub repo as a scrubbed export.

The private repo (this one) keeps its full history. The public repo gets a
fresh commit per sync containing only `git archive HEAD` minus rendered
artifacts (reports/, via .gitattributes export-ignore). Git-ignored files
(*.local.yaml, data/*.db, config/settrade.yaml) can never be in an archive.

Safety gates, in order: leak grep over the export, forbidden-file check,
full pytest run inside the export, then (unless --no-push) commit + push.

Usage:  .venv/bin/python scripts/publish_source.py [--no-push] [-m "message"]
"""
import argparse
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import PROJECT_ROOT  # noqa: E402

PUBLIC_REPO = "huachxng/DAEMON"
PUBLIC_DIR = PROJECT_ROOT / "public"            # git-ignored clone of the public repo
DEFAULT_AUTHOR = "huachxng <286653590+huachxng@users.noreply.github.com>"   # GitHub no-reply; override in publish.local.yaml
PATTERNS_FILE = PROJECT_ROOT / "config" / "publish.local.yaml"   # git-ignored on purpose:
# the leak patterns ARE the secrets (account numbers, addresses, hostnames).
FORBIDDEN = ["config/settings.local.yaml", "config/universe.local.yaml",
             "config/settrade.yaml", "data/market.db", "reports"]


def sh(*args, cwd=PROJECT_ROOT, check=True):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)


def export(dest: Path):
    tar_path = dest.parent / "export.tar"
    with open(tar_path, "wb") as f:
        subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=PROJECT_ROOT, stdout=f, check=True)
    with tarfile.open(tar_path) as tar:
        tar.extractall(dest, filter="data")
    tar_path.unlink()


def load_private() -> dict:
    import yaml
    if not PATTERNS_FILE.exists():
        sys.exit(f"missing {PATTERNS_FILE.name} — copy publish.local.example.yaml and list what must never leave")
    return yaml.safe_load(PATTERNS_FILE.read_text()) or {}


def load_patterns() -> list:
    pats = load_private().get("leak_patterns") or []
    if len(pats) < 3:
        sys.exit("publish.local.yaml has fewer than 3 leak patterns — refusing to publish on an empty gate")
    return pats


def gate_leaks(root: Path) -> list:
    hits = []
    patterns = load_patterns()
    for path in root.rglob("*"):
        if path.is_dir() or path.suffix in (".png", ".db"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in patterns:
            for m in re.finditer(pat, text):
                line = text.count("\n", 0, m.start()) + 1
                hits.append(f"{path.relative_to(root)}:{line}: {pat}")
    return hits


def gate_forbidden(root: Path) -> list:
    return [f for f in FORBIDDEN if (root / f).exists()]


def gate_tests(root: Path) -> bool:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=root, capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
    return r.returncode == 0


def sync_public(src: Path, message: str, push: bool):
    if not (PUBLIC_DIR / ".git").exists():
        PUBLIC_DIR.mkdir(exist_ok=True)
        sh("git", "init", "-b", "main", cwd=PUBLIC_DIR)
        sh("git", "remote", "add", "origin", f"https://github.com/{PUBLIC_REPO}.git", cwd=PUBLIC_DIR)
        sh("git", "fetch", "origin", cwd=PUBLIC_DIR, check=False)
        sh("git", "reset", "--hard", "origin/main", cwd=PUBLIC_DIR, check=False)
    for item in PUBLIC_DIR.iterdir():
        if item.name == ".git":
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()
    shutil.copytree(src, PUBLIC_DIR, dirs_exist_ok=True)
    sh("git", "add", "-A", cwd=PUBLIC_DIR)
    name, email = (load_private().get("author") or DEFAULT_AUTHOR).rsplit(" <", 1)
    c = sh("git", "-c", f"user.name={name}", "-c", f"user.email={email.rstrip('>')}",
           "commit", "-q", "-m", message, cwd=PUBLIC_DIR, check=False)
    if "nothing to commit" in (c.stdout + c.stderr):
        print("public tree unchanged")
    else:
        print("committed:", sh("git", "log", "--oneline", "-1", cwd=PUBLIC_DIR).stdout.strip())
    if push:
        p = sh("git", "push", "-u", "origin", "main", cwd=PUBLIC_DIR, check=False)
        print("pushed" if p.returncode == 0 else f"PUSH FAILED: {p.stderr.strip()[-300:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("-m", default=f"Sync {date.today().isoformat()}")
    a = ap.parse_args()
    if sh("git", "status", "--porcelain").stdout.strip():
        sys.exit("working tree not clean — commit first (the export is taken from HEAD)")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "export"
        root.mkdir()
        export(root)
        leaks = gate_leaks(root)
        forbidden = gate_forbidden(root)
        if leaks or forbidden:
            print("\n".join(leaks + [f"forbidden file present: {f}" for f in forbidden]))
            sys.exit("ABORTED: export is not clean")
        print(f"export clean: {sum(1 for p in root.rglob('*') if p.is_file())} files, no leak patterns")
        if not gate_tests(root):
            sys.exit("ABORTED: tests fail inside the export")
        sync_public(root, a.m, push=not a.no_push)


if __name__ == "__main__":
    main()
