"""Config loading: local overrides and symbol resolution."""
import copy

import yaml

from src import config
from src.config import CONFIG_DIR, load_universe, all_yahoo_symbols


def test_set_watchlist_names_get_bk_suffix():
    uni = load_universe()
    symbols = all_yahoo_symbols(uni)
    assert "PTT.BK" in symbols          # SET name suffixed
    assert "AAPL" in symbols            # US name untouched
    assert "THB=X" in symbols           # FX included


def test_local_override_deep_merges_over_base(tmp_path, monkeypatch):
    (tmp_path / "x.yaml").write_text("a: 1\nb: {c: 2, d: 3}\nl: [1]\n")
    (tmp_path / "x.local.yaml").write_text("b: {d: 4}\nl: [9, 9]\n")
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    assert config._load("x.yaml") == {"a": 1, "b": {"c": 2, "d": 4}, "l": [9, 9]}


def test_missing_local_file_is_fine(tmp_path, monkeypatch):
    (tmp_path / "x.yaml").write_text("a: 1\n")
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    assert config._load("x.yaml") == {"a": 1}


def test_example_local_holdings_resolve_to_yahoo_tickers():
    """The committed example must work for a fresh clone with no private file."""
    base = copy.deepcopy(load_universe())
    example = yaml.safe_load((CONFIG_DIR / "universe.local.example.yaml").read_text())
    symbols = all_yahoo_symbols(config._merge(base, example))
    for holding in example["real_holdings"]:
        assert holding["yahoo"] in symbols
