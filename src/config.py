"""Load the YAML configs and resolve every universe name to a Yahoo symbol."""
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def _merge(base: dict, override: dict) -> dict:
    """Deep-merge override into base: dicts recurse, everything else replaces."""
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def _load(name: str) -> dict:
    """config/<name>, then config/<stem>.local.yaml layered on top if present.

    The .local.yaml files are git-ignored: personal holdings, broker cash and
    anything else that belongs to one person's account live there, so the
    committed config stays publishable. See config/*.local.example.yaml.
    """
    with open(CONFIG_DIR / name) as f:
        base = yaml.safe_load(f) or {}
    local = CONFIG_DIR / name.replace(".yaml", ".local.yaml")
    if local.exists():
        with open(local) as f:
            _merge(base, yaml.safe_load(f) or {})
    return base


def load_settings() -> dict:
    return _load("settings.yaml")


def load_universe() -> dict:
    return _load("universe.yaml")


def load_rules() -> dict:
    return _load("rules.yaml")


def all_yahoo_symbols(universe: dict) -> dict:
    """{yahoo_symbol: info} for everything we track.

    info keys: kind ('dr' | 'set' | 'us' | 'benchmark' | 'fx'), and for DRs
    the original ticker/underlying/ratio from universe.yaml.
    """
    symbols: dict = {}
    for h in universe.get("real_holdings", []) + universe.get("closed_positions", []):
        if h.get("yahoo"):
            symbols[h["yahoo"]] = {"kind": "dr", **h}
    for name in universe.get("watchlist", {}).get("set", []):
        symbols[f"{name}.BK"] = {"kind": "set", "ticker": name}
    for name in universe.get("watchlist", {}).get("us", []):
        symbols[name] = {"kind": "us", "ticker": name}
    for pair in universe.get("dr_map", []):
        symbols.setdefault(pair["underlying"], {"kind": "us", "ticker": pair["underlying"]})
        symbols.setdefault(pair["dr"], {"kind": "dr", "ticker": pair["dr"]})
    symbols.setdefault("NDX01.BK", {"kind": "dr", "ticker": "NDX01.BK"})
    for name in universe.get("watchlist", {}).get("macro", []):
        symbols.setdefault(name, {"kind": "macro", "ticker": name})
    b = universe.get("benchmarks", {})
    for key in ("set", "set_fallback", "us"):
        if b.get(key):
            symbols[b[key]] = {"kind": "benchmark", "ticker": b[key]}
    if b.get("fx"):
        symbols[b["fx"]] = {"kind": "fx", "ticker": b["fx"]}
    return symbols
