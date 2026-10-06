"""Alert rules — pure functions over prepared inputs.

Hand cases:
- concentration: weight 30% vs 25% threshold -> fires with the number in both languages
- concentration, benchmark ETF: TDEX.BK is the DESIGNED Thai sleeve (45% paper /
  25% live), so it is judged against sleeve + 5% tolerance, not the 25% cap.
  Paper TDEX at 44.9% -> silent; at 52% -> fires against the 50% ceiling.
- floor proximity: warn at 165k, urgent at 157k:
    equity 170k -> nothing; 163k -> info; 156k -> urgent
- volume anomaly: today 400 vs 20d avg 100 = 4x >= 3x -> fires
"""
import pandas as pd
import pytest

from src.alerts.engine import DAEMON_BOOKS, evaluate
from src.alerts.rules import check_concentration, check_floor, check_volume_anomaly
from src.config import load_rules, load_settings, load_universe
from src.datafeed.store import Store


def test_concentration_fires_above_threshold():
    alerts = check_concentration({"GOLD19.BK": 30.0, "META01.BK": 20.0},
                                 threshold_pct=25, book="real")
    assert len(alerts) == 1
    a = alerts[0]
    assert a.rule_id == "concentration" and a.severity == "urgent"
    assert "GOLD19" in a.msg_en and "30.0%" in a.msg_en
    assert "30.0%" in a.msg_th


def test_concentration_quiet_below_threshold():
    assert check_concentration({"A": 20.0, "B": 20.0}, 25, "real") == []


def test_floor_proximity_ladder():
    assert check_floor(170_000, warn_at=165_000, urgent_at=157_000) == []
    info = check_floor(163_000, warn_at=165_000, urgent_at=157_000)
    assert len(info) == 1 and info[0].severity == "info"
    urgent = check_floor(156_000, warn_at=165_000, urgent_at=157_000)
    assert len(urgent) == 1 and urgent[0].severity == "urgent"


def test_volume_anomaly_fires_at_multiple():
    alerts = check_volume_anomaly("PTT.BK", today_volume=400, avg20=100, multiple=3)
    assert len(alerts) == 1 and "4.0x" in alerts[0].msg_en


def test_volume_anomaly_quiet_on_normal_volume():
    assert check_volume_anomaly("PTT.BK", 150, 100, 3) == []


# --- the benchmark ETF is big ON PURPOSE ------------------------------------
# TDEX.BK is the whole Thai sleeve. Before this exemption every evening run
# logged an URGENT "TDEX is 44.9% of the paper book (limit 25%)" and pushed it
# to the user's phone — alarm fatigue on a position the strategy designed.

def test_benchmark_silent_at_its_designed_sleeve():
    alerts = check_concentration({"TDEX.BK": 44.9}, threshold_pct=25, book="paper",
                                 benchmark="TDEX.BK", benchmark_limit_pct=50)
    assert alerts == []


def test_benchmark_fires_only_past_its_own_ceiling():
    alerts = check_concentration({"TDEX.BK": 52.0}, threshold_pct=25, book="paper",
                                 benchmark="TDEX.BK", benchmark_limit_pct=50)
    assert len(alerts) == 1
    assert "limit 50%" in alerts[0].msg_en and "52.0%" in alerts[0].msg_en


def test_live_sleeve_at_target_does_not_flap():
    # LIVE sleeve is 25% by design; once the BUY 3,800 TDEX fills it sits at
    # ~24.8% and small moves must NOT toggle an urgent push either way.
    for weight in (24.8, 25.0, 25.4, 29.9):
        assert check_concentration({"TDEX.BK": weight}, 25, "live",
                                   benchmark="TDEX.BK", benchmark_limit_pct=30) == []
    assert len(check_concentration({"TDEX.BK": 30.1}, 25, "live",
                                   benchmark="TDEX.BK", benchmark_limit_pct=30)) == 1


def test_exemption_covers_only_the_benchmark():
    # A momentum DR at 30% is still a genuine breach, in the same call.
    alerts = check_concentration({"TDEX.BK": 44.9, "MSFT01.BK": 30.0}, 25, "paper",
                                 benchmark="TDEX.BK", benchmark_limit_pct=50)
    assert len(alerts) == 1 and "MSFT01" in alerts[0].msg_en
    assert "limit 25%" in alerts[0].msg_en


def test_no_benchmark_configured_means_ordinary_cap():
    # Defaults keep the old behaviour: everything judged against threshold_pct.
    assert len(check_concentration({"TDEX.BK": 44.9}, 25, "paper")) == 1


# --- the Thai message must not lie about whose money it is ------------------

def test_thai_label_calls_the_live_book_real_money():
    a = check_concentration({"MSFT01.BK": 30.0}, 25, "live")[0]
    assert "เงินจริง" in a.msg_th        # live = real money, user executes it
    assert "จำลอง" not in a.msg_th       # ...and never "simulated"


def test_thai_label_still_right_for_paper_and_real():
    assert "จำลอง" in check_concentration({"A": 30.0}, 25, "paper")[0].msg_th
    assert "พอร์ตจริง" in check_concentration({"A": 30.0}, 25, "real")[0].msg_th


# --- config and engine must agree -------------------------------------------

def test_rules_yaml_applies_to_matches_the_books_the_engine_evaluates():
    rules = {r["id"]: r for r in load_rules()["rules"]}
    for rule_id in ("concentration", "volume_anomaly", "paper_circuit_breaker"):
        assert set(rules[rule_id]["applies_to"]) == set(DAEMON_BOOKS), rule_id
    # 'real' is report-only: no daemon rule may claim to fire on it.
    assert "real" not in DAEMON_BOOKS


def test_live_benchmark_sleeve_matches_settings():
    # The alert ceiling is only honest if it tracks the strategy's real sleeve.
    conc = {r["id"]: r for r in load_rules()["rules"]}["concentration"]
    tdex_sleeve = load_settings()["books"]["live"]["sleeves"]["tdex"]
    assert conc["benchmark_sleeve_pct"]["live"] == pytest.approx(100 * tdex_sleeve)


# --- end to end, on a temp DB (never data/market.db) ------------------------

def _bars(date, close):
    return pd.DataFrame([{"date": date, "open": close, "high": close, "low": close,
                          "close": close, "adj_close": close, "volume": 1000}])


ENGINE_SETTINGS = {"books": {
    "live": {"start_cash_thb": 200_000, "halt_buys_below_thb": 160_000,
             "liquidate_below_thb": 155_000, "hard_floor_thb": 150_000},
    "paper": {"start_cash_thb": 200_000, "halt_buys_below_thb": 160_000,
              "liquidate_below_thb": 155_000, "hard_floor_thb": 150_000},
}}


def _store_with_paper_tdex(tmp_path, qty, price):
    store = Store(tmp_path / "alerts.db")       # temp DB — never data/market.db
    store.upsert_fx([("2026-08-19", 33.0)])
    store.upsert_prices("TDEX.BK", _bars("2026-08-19", price))
    store.insert_trade(book="paper", ticker="TDEX.BK", side="BUY", qty=qty,
                       price=price, fees=0.0, ts="2026-08-19")
    return store


def test_engine_is_quiet_on_the_designed_paper_sleeve(tmp_path):
    # 9,000 units @ ฿10 = ฿90,000 of a ฿200,000 book = exactly the 45% sleeve.
    store = _store_with_paper_tdex(tmp_path, qty=9_000, price=10.0)
    assert [a for a in evaluate(store, ENGINE_SETTINGS)
            if a.rule_id == "concentration"] == []


def test_engine_still_fires_on_a_genuine_benchmark_breach(tmp_path):
    # Same units, but TDEX doubled: ฿180,000 of a ฿290,000 book = 62% > 50%.
    store = _store_with_paper_tdex(tmp_path, qty=9_000, price=10.0)
    store.upsert_prices("TDEX.BK", _bars("2026-08-20", 20.0))
    hits = [a for a in evaluate(store, ENGINE_SETTINGS) if a.rule_id == "concentration"]
    assert len(hits) == 1 and hits[0].severity == "urgent"
    assert "TDEX" in hits[0].msg_en
