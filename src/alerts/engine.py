"""Evaluate every alert rule against current store state and log the hits."""
from datetime import datetime, timezone, timedelta

from src.config import load_rules, load_universe
from src.alerts.rules import Alert, check_concentration, check_floor, check_volume_anomaly
from src.paperbot.bot import paper_snapshot

ICT = timezone(timedelta(hours=7))

# The books this engine actually evaluates. The 'real' book is REPORT-ONLY —
# the user manages their own BLS positions ("Don't manage my own stock",
# 2026-08-14) — so no rule fires on it. config/rules.yaml applies_to must match.
DAEMON_BOOKS = ("live", "paper")


def _rule(rules, rule_id):
    return next(r for r in rules["rules"] if r["id"] == rule_id)


def evaluate(store, settings) -> list:
    rules = load_rules()
    alerts: list[Alert] = []

    # Daemon books only (user manages their personal positions themselves —
    # requested 2026-08-14: "Don't manage my own stock").
    conc = _rule(rules, "concentration")
    floor = _rule(rules, "floor_proximity_real")
    # The benchmark ETF (TDEX.BK) IS the Thai sleeve, so it is allowed its
    # designed weight plus a tolerance instead of the ordinary per-name cap —
    # otherwise a by-design 45% paper sleeve pages the user every evening.
    benchmark = load_universe()["benchmarks"]["set_fallback"]
    sleeve_pct = conc.get("benchmark_sleeve_pct") or {}
    tolerance = conc.get("benchmark_tolerance_pct", 0)
    snaps = {}
    for book in DAEMON_BOOKS:
        snap = paper_snapshot(store, settings, book=book)
        snaps[book] = snap
        if snap["rows"]:
            weights = {r["ticker"]: 100 * r["value"] / snap["equity"] for r in snap["rows"]}
            # No configured sleeve for this book -> no exemption, ordinary cap.
            designed = sleeve_pct.get(book)
            alerts += check_concentration(
                weights, conc["threshold_pct"], book,
                benchmark=benchmark,
                benchmark_limit_pct=None if designed is None else designed + tolerance)
        if snap["state"] != "normal":
            alerts.append(Alert(
                f"{book}_circuit_breaker", "urgent",
                f"{book.upper()} book circuit breaker: {snap['state'].upper()} "
                f"at equity ฿{snap['equity']:,.0f}",
                f"เบรกเกอร์พอร์ต {book} ทำงาน: {snap['state'].upper()} "
                f"ที่มูลค่า ฿{snap['equity']:,.0f}",
            ))
    # The 150k floor guards the daemon's LIVE sleeve.
    alerts += check_floor(snaps["live"]["equity"],
                          floor["warn_at_thb"], floor["urgent_at_thb"])

    # Volume anomalies on names the daemon holds or has ticketed
    vol_rule = _rule(rules, "volume_anomaly")
    tickers = {r["ticker"] for s in snaps.values() for r in s["rows"]}
    tickers |= {o["ticker"] for s in snaps.values() for o in s["pending"]}
    for t in tickers:
        df = store.read_prices(t)
        if len(df) > 21:
            alerts += check_volume_anomaly(
                t, float(df["volume"].iloc[-1]),
                float(df["volume"].iloc[-21:-1].mean()), vol_rule["multiple"])

    now = datetime.now(ICT).isoformat(timespec="minutes")
    for a in alerts:
        store.conn.execute(
            "INSERT INTO alerts_log (rule_id, ts, message_en, message_th, delivered_via) "
            "VALUES (?, ?, ?, ?, ?)", (a.rule_id, now, a.msg_en, a.msg_th, "pending"))
    store.conn.commit()
    return alerts
