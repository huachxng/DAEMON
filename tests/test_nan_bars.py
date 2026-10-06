"""Bars without a close (in-progress extended sessions) must not poison anything.

Yahoo publishes today's Thai DR bar DURING the overnight session with
open/high/low/volume but close=NaN. Regression tests for 2026-08-15.
"""
import pandas as pd

from src.datafeed.fetch import _normalize
from src.datafeed.store import Store
from src.paperbot.bot import _bar


def test_normalize_drops_rows_without_close():
    raw = pd.DataFrame({
        "Date": pd.to_datetime(["2026-08-13", "2026-08-14"]),
        "Open": [10.0, 10.5], "High": [10.2, 10.6], "Low": [9.9, 10.4],
        "Close": [10.1, float("nan")], "Adj Close": [10.1, float("nan")],
        "Volume": [1000, 500],
    })
    out = _normalize(raw)
    assert list(out["date"]) == ["2026-08-13"]


def test_bar_skips_trailing_nan_close(tmp_path):
    store = Store(tmp_path / "t.db")
    bars = pd.DataFrame([
        {"date": "2026-08-13", "open": 49.5, "high": 50.3, "low": 49.5,
         "close": 50.25, "adj_close": 50.25, "volume": 1000},
        {"date": "2026-08-14", "open": 51.0, "high": 51.3, "low": 50.3,
         "close": float("nan"), "adj_close": float("nan"), "volume": 500},
    ])
    store.upsert_prices("ASML01.BK", bars)
    date, px = _bar(store, "ASML01.BK", "close")
    assert px == 50.25
    assert date == "2026-08-13"
