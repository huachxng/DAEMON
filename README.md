# DAEMON

A rules-based trading daemon for Thai-listed depositary receipts (DRs) on US
stocks, run as a two-month live experiment on the Stock Exchange of Thailand
starting 15 August 2026. Internal code name: CLAUDE TRADE.

The daemon pulls end-of-day data, ranks a universe of US underlyings by
momentum, converts the picks into orders on their SET-listed DRs, and issues
**order tickets**. A human places every order at the broker. The daemon never
touches an account. It then tracks fills, enforces protective exits, defends a
hard capital floor, and publishes a bilingual (Thai/English) ledger.

Live results, order log and risk plan: **https://huachxng.github.io/ct-da09852e/**

## How it decides

| Layer | Rule |
|---|---|
| Signal | Top-3 of 14 US underlyings by 126-day return, only if above their 200-day average |
| Execution | Orders go on the matching SET DR (`config/universe.yaml` → `dr_map`); DRs trade a night session that tracks US hours |
| Sizing | 55% momentum sleeve, 25% SET50 ETF (TDEX), ~20% cash; 20% cap per name; no ticket under ฿10k except full exits |
| Re-pick | Quarterly. Between re-picks the book converges to persisted targets |
| Exits | Hard stop −20% from cost · trend break (underlying < 200-day average) · rotation at re-pick |
| Floor | ≤฿160k halve every target · ≤฿155k liquidate · ฿150k unreachable by construction |
| Costs | Bualuang all-in 0.2215% per side, calibrated from real fills (no minimum) |

Three books share one SQLite ledger: **live** (the daemon's real-money sleeve,
human-executed), **personal** (the owner's own positions, report-only, never
advised on), and **paper** (an autonomous US-stock sandbox).

## What the backtests said

All in `docs/backtests/`, run in THB with real fees and DR spread costs on an
honest engine (decide on close, fill at next open, slippage against you):

- Thai-stock momentum loses to holding the SET50 ETF after fees. Rejected.
- US momentum via DRs: top-3 quarterly beat the survivorship-matched equal-weight control; chosen.
- Faster rotation (weekly, fortnightly) is worse after costs; parameter "optimisation" has ~0 rank correlation out of sample.
- Every take-profit rule tested made less money than holding winners with stops; a fixed +25% target cut four-year growth from 6.1x to 2.9x.

## Layout

```
config/     settings, rules, universe, earnings calendar — all behaviour is declared here
            *.local.yaml (git-ignored) hold one person's holdings and cash; examples committed
src/        datafeed · portfolio (FIFO lots, fees, SET ticks) · risk (exits, stop-watch, radar,
            performance) · backtest · paperbot (daily decision) · digest (reports, levels) · alerts
scripts/    update.py (data) · daily_run.py (decide + tickets) · log_trade.py / log_order.py
            (fills, placed, cancelled) · report.py · risk_plan.py · performance.py ·
            build_dashboard.py + publish_github.py (ledger site) · stop_watch.py · radar.py ·
            settrade_sync.py (read-only broker reconciliation) · publish_source.py (this repo)
tests/      pytest; every piece of financial math is checked against hand-computed cases
docs/       trading rules, graded lessons, backtest write-ups
data/       market.db (git-ignored): prices, trades, tickets, order events, journal, equity
```

## Running it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp config/settings.local.example.yaml config/settings.local.yaml   # your cash figures
cp config/universe.local.example.yaml config/universe.local.yaml   # your holdings
.venv/bin/python scripts/update.py       # pull EOD prices, FX, dividends
.venv/bin/python scripts/daily_run.py    # decide, print tickets, snapshot equity
.venv/bin/python scripts/report.py       # bilingual HTML report
.venv/bin/python -m pytest               # test suite
```

Fills are logged by hand (`scripts/log_trade.py live BUY MSFT01.BK 3700 4.82 --fees 39.50`)
or reconciled read-only from the Settrade Open API (`config/settrade.example.yaml`).

## Limitations, stated plainly

- Free end-of-day data (Yahoo Finance). No intraday anything.
- The DR universe is hindsight-picked: only names that earned a Thai DR are in it, so absolute backtest returns are inflated. Comparisons between rules are what the backtests are for.
- Signals use the US underlying; DR premium/discount and thin night-session liquidity are not modelled.
- Two months is not a track record.

**Not investment advice.** This is one person's bookkeeping and a coded rulebook,
published so the reasoning can be read and the mistakes can be seen.

## License

MIT.
