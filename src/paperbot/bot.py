"""The autonomous paper-trading daemon's daily cycle.

Run after market close (data already updated). Steps:
  1. Fill yesterday's pending orders at today's OPEN (never same-day close).
  2. Mark the book to market in THB (US names via FX).
  3. Circuit breaker check — 'liquidate' turns everything into sell orders.
  4. Strategy decisions (declared in docs/trading-rules.md):
       Thai sleeve 45%: hold TDEX.BK (null strategy — SET momentum failed backtest)
       US sleeve 45%:   TopNMomentum top-5, monthly (bootstraps on first run)
       ~10% cash buffer by construction.
  5. New orders go to pending (fill at tomorrow's open); everything journaled.

All stored paper trade prices are THB (US fills converted at that day's FX,
native USD price kept in the note) so the ledger stays single-currency.
"""
from datetime import datetime, timezone, timedelta

import json
import math

import pandas as pd

from src.config import load_universe, load_settings
from src.portfolio.ledger import build_positions, cash_after_trades
from src.portfolio.fees import thai_fee, us_paper_fee
from src.backtest.momentum import TopNMomentum
from src.paperbot.breaker import breaker_state
from src.paperbot.sizing import (apply_user_overrides, drop_dust,
                                 orders_from_targets, pick_affordable)

ICT = timezone(timedelta(hours=7))
SLIPPAGE = {"thai": 10, "us": 10}  # bps, liquid names


def _bar(store, ticker, field):
    df = store.read_prices(ticker)
    df = df[df[field].notna()]   # ignore in-progress bars (NaN close/open)
    if df.empty:
        return None, None
    return df["date"].iloc[-1], float(df[field].iloc[-1])


def _price_thb(store, ticker, field, fx):
    date, px = _bar(store, ticker, field)
    if px is None:
        return None, None
    if not ticker.endswith(".BK") and not ticker.startswith("^"):
        return date, px * fx
    return date, px


def paper_snapshot(store, settings, book="paper") -> dict:
    """Everything the report and the bot need to know about a daemon book."""
    fx = store.latest_fx() or 33.0
    trades = store.read_trades(book)
    start = settings["books"][book]["start_cash_thb"]
    cash = cash_after_trades(start, trades)
    positions = build_positions(trades)
    rows, value = [], 0.0
    for t, p in sorted(positions.items()):
        if p.qty <= 0:
            continue
        _, px = _price_thb(store, t, "close", fx)
        v = p.qty * (px or 0)
        value += v
        rows.append({"ticker": t, "qty": p.qty, "price_thb": px, "value": v,
                     "unrealized": v - p.cost_basis})
    equity = cash + value
    return {"fx": fx, "cash": cash, "value": value, "equity": equity,
            "rows": rows, "state": breaker_state(equity, settings),
            "pending": store.unfilled_orders(book),
            "realized": sum(p.realized_pl for p in positions.values())}


def fill_pending(store, settings, today_iso) -> list:
    """Fill any pending order whose creation day is behind today's bar."""
    fx = store.latest_fx() or 33.0
    filled = []
    for order in store.unfilled_orders("paper"):
        bar_date, open_thb = _price_thb(store, order["ticker"], "open", fx)
        if open_thb is None or bar_date <= (order["after_date"] or order["created_ts"][:10]):
            continue  # that market hasn't printed a NEW bar since the decision
        is_thai = order["ticker"].endswith(".BK")
        slip = SLIPPAGE["thai" if is_thai else "us"] / 10_000
        px = open_thb * (1 + slip if order["side"] == "BUY" else 1 - slip)
        if is_thai:
            fee = thai_fee(order["qty"] * px, settings)
        else:
            fee = us_paper_fee(order["qty"], settings) * fx
        note = f"paperbot fill at {bar_date} open"
        if not is_thai:
            _, native = _bar(store, order["ticker"], "open")
            note += f" ({native:.2f} USD, fx {fx:.2f})"
        store.insert_trade(book="paper", ticker=order["ticker"], side=order["side"],
                           qty=order["qty"], price=round(px, 4), fees=round(fee, 2),
                           ts=bar_date, note=note)
        store.mark_order_filled(order["id"])
        store.insert_journal(ts=today_iso, book="paper",
                             action=f"FILL {order['side']} {order['qty']:g} {order['ticker']} @ ฿{px:,.2f}",
                             reasoning=note, rule_id="fill")
        filled.append(order)
    return filled


def decide(store, settings, today_iso) -> list:
    """Compute new target orders and queue them as pending."""
    uni = load_universe()
    snap = paper_snapshot(store, settings)
    fx = snap["fx"]
    held = {r["ticker"]: r["qty"] for r in snap["rows"]}
    tdex = uni["benchmarks"]["set_fallback"]

    if snap["state"] == "liquidate":
        orders = [type("O", (), {"ticker": t, "side": "SELL", "qty": q})()
                  for t, q in held.items()]
        reason = (f"CIRCUIT BREAKER: equity ฿{snap['equity']:,.0f} <= liquidate line "
                  f"฿{settings['books']['paper']['liquidate_below_thb']:,}. All to cash; "
                  "halted until user review.")
    else:
        targets = {tdex: 0.45}
        us_names = uni["watchlist"]["us"]
        closes = pd.DataFrame({
            t: pd.Series(store.read_prices(t)["close"].values,
                         index=pd.to_datetime(store.read_prices(t)["date"]))
            for t in us_names
        })
        strat = TopNMomentum(n=5, lookback=126, sma_filter=200)
        has_us = any(not t.endswith(".BK") for t in held)
        # Monthly gate when invested; bootstrap ranking on the very first run.
        gate_open = not has_us or strat.target_weights(closes) is not None
        reason_us = "bootstrap ranking (first run)" if not has_us else \
            ("monthly rebalance signal" if gate_open else "no signal until month boundary")
        us_prices_thb = {}
        for t in us_names:
            _, px = _price_thb(store, t, "close", fx)
            us_prices_thb[t] = px
        if gate_open:
            slot = 0.09 * snap["equity"]  # 45% sleeve / 5 slots
            ranking = strat.ranked(closes) or []
            picks = pick_affordable(ranking, us_prices_thb, slot_thb=slot, n=5)
            skipped = [t for t in ranking[:5] if t not in picks]
            for t in us_names:
                targets[t] = 0.09 if t in picks else 0.0
            reason = (f"Thai sleeve: hold TDEX 45% (null strategy — SET momentum failed "
                      f"backtest). US sleeve 45%: top-5 AFFORDABLE by 126d momentum "
                      f"({reason_us}): {', '.join(picks)}."
                      + (f" Substituted out (1 share > ฿{slot:,.0f} slot): "
                         f"{', '.join(skipped)}." if skipped else "")
                      + f" Cash buffer ~10%. Breaker: {snap['state']}.")
        else:
            reason = (f"Thai sleeve: maintain TDEX 45%. US sleeve: {reason_us}, "
                      f"holding current names. Breaker: {snap['state']}.")

        prices = dict(us_prices_thb)
        _, prices[tdex] = _price_thb(store, tdex, "close", fx)
        orders = orders_from_targets(snap["equity"], targets, held, prices,
                                     lot_sizes={tdex: 100})
        if snap["state"] == "halt_buys":
            orders = [o for o in orders if o.side == "SELL"]
            reason += " HALT_BUYS active: buy orders suppressed."

    store.cancel_unfilled("paper")  # today's decision supersedes anything queued
    for o in orders:
        store.insert_pending_order(book="paper", ticker=o.ticker, side=o.side,
                                   qty=o.qty, created_ts=today_iso,
                                   after_date=store.last_price_date(o.ticker))
    action = ("queue " + ", ".join(f"{o.side} {o.qty:g} {o.ticker}" for o in orders)
              ) if orders else "no orders"
    store.insert_journal(ts=today_iso, book="paper", action=action,
                         reasoning=reason, rule_id="daily-decision")
    return orders


def decide_live(store, settings, today_iso) -> list:
    """The REAL-money sleeve: emit order TICKETS for the user to execute.

    Never auto-fills — a live pending order clears only when the user logs the
    actual execution (scripts/log_trade.py live ...). Universe: TDEX + verified
    DRs. Momentum is ranked on the US underlyings (5y of data); the ticket is
    written on the SET-listed DR the account can actually trade.
    """
    uni = load_universe()
    cfg = settings["books"]["live"]
    snap = paper_snapshot(store, settings, book="live")
    held = {r["ticker"]: r["qty"] for r in snap["rows"]}
    tdex = uni["benchmarks"]["set_fallback"]
    dr_map = {p["underlying"]: p["dr"] for p in uni["dr_map"]}

    if snap["state"] == "liquidate":
        orders = [type("O", (), {"ticker": t, "side": "SELL", "qty": q})()
                  for t, q in held.items()]
        reason = (f"CIRCUIT BREAKER on LIVE sleeve: equity ฿{snap['equity']:,.0f} <= "
                  f"฿{cfg['liquidate_below_thb']:,}. Liquidation tickets issued — "
                  "EXECUTE THESE, then we review together.")
    else:
        closes = pd.DataFrame({
            u: pd.Series(store.read_prices(u)["close"].values,
                         index=pd.to_datetime(store.read_prices(u)["date"]))
            for u in dr_map
        })
        top_n = cfg.get("momentum_top_n", 5)
        strat = TopNMomentum(n=top_n, lookback=126, sma_filter=200,
                             rebalance_every=cfg["rebalance_every_months"])
        # Picks are PERSISTED: chosen at bootstrap and at quarterly boundaries.
        # Between boundaries we keep converging toward the persisted targets, so
        # partially-filled allocations are completed instead of forgotten.
        persisted = store.get_state("live_targets")
        # Month boundary on the price calendar AND >= rebalance_every months
        # since the last pick (persisted — a fresh strategy object per run
        # would otherwise re-pick every month; bug found 2026-08-19).
        from src.backtest.momentum import is_repick_due
        month_turned = (len(closes) >= 2
                        and closes.index[-1].month != closes.index[-2].month)
        at_boundary = month_turned and is_repick_due(
            store.get_state("live_last_repick"), today_iso,
            cfg["rebalance_every_months"])
        if persisted is None or at_boundary:
            store.set_state("live_last_repick", today_iso[:10])
            ranking = strat.ranked(closes) or []
            picks_u = ranking[:top_n]
            slot = cfg["sleeves"]["dr_momentum"] / top_n
            targets = {tdex: cfg["sleeves"]["tdex"]}
            for u, dr in dr_map.items():
                targets[dr] = slot if u in picks_u else 0.0
            store.set_state("live_targets", json.dumps(targets))
            picks_str = ", ".join(f"{u}→{dr_map[u].replace('.BK', '')}" for u in picks_u)
            reason = (f"LIVE sleeve {'quarterly rebalance' if persisted else 'bootstrap'}: "
                      f"top-{top_n} 126d momentum on DR underlyings = {picks_str}. "
                      f"Sleeves: TDEX {cfg['sleeves']['tdex']:.0%} + momentum "
                      f"{cfg['sleeves']['dr_momentum']:.0%}, ~30% cash (sized so the "
                      f"backtest's 29% maxDD cannot reach the 150k floor). "
                      f"Breaker: {snap['state']}.")
        else:
            targets = json.loads(persisted)
            reason = (f"LIVE sleeve: converging to persisted targets (next re-pick at "
                      f"the quarterly boundary). Breaker: {snap['state']}.")

        # Daily protective exits: hard stop (-20% from cost) and trend break
        # (underlying < SMA200). A triggered name is zeroed in the persisted
        # targets -> orders_from_targets emits the SELL ticket naturally. It can
        # only re-enter at a quarterly re-pick, on fresh momentum evidence.
        from src.risk.exits import exit_signal
        u_of = {p["dr"]: p["underlying"] for p in uni["dr_map"]}
        exit_notes = []
        protected = set()   # tickers whose SELL is a floor-protecting exit
        for r in snap["rows"]:
            px = r["price_thb"]
            if not px or math.isnan(px) or not r["qty"]:
                continue
            cost_pu = (r["value"] - r["unrealized"]) / r["qty"]
            u = u_of.get(r["ticker"])
            u_close = u_sma = None
            if u:
                s = store.read_prices(u)["close"].dropna()
                if len(s) >= 200:
                    u_close, u_sma = float(s.iloc[-1]), float(s.tail(200).mean())
            sig = exit_signal(cost_pu, px, u_close, u_sma)
            if sig and targets.get(r["ticker"], 0) > 0:
                targets[r["ticker"]] = 0.0
                exit_notes.append(f"{r['ticker'].replace('.BK', '')}: {sig.upper()}")
                protected.add(r["ticker"])
        if exit_notes:
            store.set_state("live_targets", json.dumps(targets))
            reason += " ⚠️ PROTECTIVE EXITS: " + "; ".join(exit_notes) + "."

        prices = {}
        for t in list(targets):
            _, px = _price_thb(store, t, "close", store.latest_fx() or 33.0)
            prices[t] = px
        lots = {t: 100 for t in targets}   # SET board lot
        orders = orders_from_targets(snap["equity"], targets, held, prices, lots)
        if snap["state"] == "halt_buys":
            # Graduated floor defence: cut exposure now, don't wait for 155k.
            from src.paperbot.sizing import scale_targets
            targets = scale_targets(targets, cfg.get("halt_derisk_factor", 0.5))
            orders = orders_from_targets(snap["equity"], targets, held, prices, lots)
            orders = [o for o in orders if o.side == "SELL"]
            reason += (f" HALT_BUYS: equity ≤ ฿{cfg['halt_buys_below_thb']:,} — targets halved, "
                       "SELL tickets issued to defend the floor; buys suppressed.")
        orders = drop_dust(orders, prices, targets, cfg["min_ticket_notional_thb"])
        overrides = json.loads(store.get_state("user_overrides") or "{}")
        before = {(o.side, o.ticker) for o in orders}
        orders = apply_user_overrides(orders, overrides, protected)
        dropped = before - {(o.side, o.ticker) for o in orders}
        if dropped:
            reason += (" USER OVERRIDE honoured (hold): " +
                       ", ".join(t.replace(".BK", "") for _, t in sorted(dropped)) +
                       " — rotation sell not ticketed; protective exits still apply.")

    store.cancel_unfilled("live")
    for o in orders:
        store.insert_pending_order(book="live", ticker=o.ticker, side=o.side,
                                   qty=o.qty, created_ts=today_iso,
                                   after_date=store.last_price_date(o.ticker))
    action = ("TICKETS: " + ", ".join(f"{o.side} {o.qty:g} {o.ticker}" for o in orders)
              ) if orders else "no tickets"
    store.insert_journal(ts=today_iso, book="live", action=action,
                         reasoning=reason, rule_id="live-decision")
    return orders


def run_day(store, settings=None) -> dict:
    settings = settings or load_settings()
    today_iso = datetime.now(ICT).strftime("%Y-%m-%d %H:%M")
    filled = fill_pending(store, settings, today_iso)
    orders = decide(store, settings, today_iso)
    tickets = decide_live(store, settings, today_iso)
    snap = paper_snapshot(store, settings)
    live = paper_snapshot(store, settings, book="live")
    return {"filled": len(filled), "queued": len(orders), "snapshot": snap,
            "tickets": tickets, "live": live}
