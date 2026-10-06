"""The SQLite store: schema creation and idempotent price upserts."""
import pandas as pd

from src.datafeed.store import Store


def make_bars(dates_closes):
    """Helper: build an EOD bars DataFrame like the datafeed produces."""
    return pd.DataFrame(
        [
            {"date": d, "open": c, "high": c, "low": c, "close": c,
             "adj_close": c, "volume": 1000}
            for d, c in dates_closes
        ]
    )


def test_upsert_prices_is_idempotent_and_latest_wins(tmp_path):
    store = Store(tmp_path / "test.db")

    store.upsert_prices("PTT.BK", make_bars([("2026-08-10", 40.0), ("2026-08-11", 41.0)]))
    # Re-upsert overlapping day with a corrected close; add a new day.
    store.upsert_prices("PTT.BK", make_bars([("2026-08-11", 41.5), ("2026-08-12", 42.0)]))

    df = store.read_prices("PTT.BK")
    assert list(df["date"]) == ["2026-08-10", "2026-08-11", "2026-08-12"]
    assert list(df["close"]) == [40.0, 41.5, 42.0]


def test_read_prices_unknown_ticker_returns_empty(tmp_path):
    store = Store(tmp_path / "test.db")
    assert store.read_prices("NOPE.BK").empty
