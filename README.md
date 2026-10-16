# DAEMON

A Python program that decides what to buy and sell on the Thai stock exchange
and tells me. I place the orders myself in the broker app. It has no access to
the account.

It trades DRs, which are Thai-listed receipts on US stocks (MICRON01 is Micron,
PLTR01 is Palantir, and so on). They trade on SET in baht, and the DR night
session follows US hours.

I started it with 200,000 baht on 15 August 2026 as a two-month experiment.
On day 60 (13 October) it was at 210,777, up 5.4%. As I write this it is at
202,248. The live ledger is here: https://huachxng.github.io/ct-da09852e/

I built it with Claude Code while learning Python. The code is deliberately
small and plain so I can read all of it.

## What it does every day

1. After the SET close it pulls end-of-day prices from Yahoo Finance for 14 US
   stocks that have Thai DRs, plus the DRs themselves, TDEX (the SET50 ETF)
   and the dollar-baht rate.
2. It ranks the 14 by their return over the last 126 trading days and keeps
   only names above their own 200-day average. The top 3 get the money, 55% of
   the book split three ways. Another 25% sits in TDEX. The rest is cash.
3. It re-picks the top 3 every three months. In between it just holds, unless
   a name falls 20% below what I paid for it or drops under its 200-day
   average. Then it sells.
4. If the book ever drops to 160,000 it halves every position. At 155,000 it
   sells everything. 150,000 is the line I told it never to cross.
5. If any of that means an order, it writes a ticket (buy 3,600 PLTR01 around
   5.15) and emails it to me. I place the order, then reply "filled 3600 PLTR01
   @ 5.15" and it logs the fill.

Most days the answer is "no tickets". It has made 12 trades in two months and
paid 453 baht in commission.

## What is in here

```
config/     settings.yaml     book sizes, floors, fee rate, sleeves
            universe.yaml     the 14 stocks and their DR tickers, watchlists
            rules.yaml        alert thresholds
            earnings.yaml     earnings dates for the names it holds
            *.local.yaml      my own holdings and cash. Not in git. Examples are.
src/        datafeed/   Yahoo download, the SQLite store, read-only Settrade sync
            portfolio/  FIFO lots, P&L, the fee model, SET tick sizes
            backtest/   a small daily backtest engine and the momentum strategy
            paperbot/   the daily decision: targets, sizing, breaker, tickets
            risk/       exits, cut-loss watchdog, earnings radar, performance math
            digest/     the HTML report and the cut-loss levels table
            alerts/     concentration and volume alerts
            options/    Black-Scholes, used by the paper book only
scripts/    update.py          pull data
            daily_run.py       decide and print tickets
            log_trade.py       record a fill
            log_order.py       record placed / cancelled
            report.py, risk_plan.py, performance.py, research_deck.py   HTML pages
            build_dashboard.py, publish_github.py   the ledger site
            stop_watch.py      warns me when a price is near a cut-loss
            radar.py           flags big moves and earnings within 5 days
            settrade_sync.py   compares the broker's positions with the ledger
            publish_source.py  pushes this repo (strips private files first)
tests/      30 files. Every bit of money math has a hand-worked example.
docs/       the rules, graded lessons, and the backtest write-ups
data/       market.db, SQLite. Prices, trades, tickets, journal, equity. Not in git.
```

There are three "books" in the database. `live` is the daemon's 200k. `paper`
is a simulated US-stock sandbox it trades on its own. `real` is my personal
account, which it only reports on.

## Running it

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp config/settings.local.example.yaml config/settings.local.yaml
cp config/universe.local.example.yaml config/universe.local.yaml
.venv/bin/python scripts/update.py
.venv/bin/python scripts/daily_run.py
.venv/bin/python -m pytest
```

## Things I learned the hard way

- Bualuang charges 0.2215% per side, all in, with no minimum. I assumed a
  50 baht minimum for a week. The real fills proved otherwise.
- The daemon once ticketed a sell of 100 AMZN06 worth 212 baht to fix a 0.1%
  drift. I executed it. It lost 9 baht. Now no ticket is under 10,000 baht
  unless it is a full exit.
- I asked it to rotate faster to make more money. The backtest said weekly
  rotation is the worst of every setting tried, because of fees and spread.
  See `docs/backtests/2026-09-21.md`.
- I asked it to take profit. Every take-profit rule tested made less than
  holding with stops, by a lot. See `docs/backtests/2026-09-24.md`.
- The broker's average cost is FIFO across the whole account, so if you hold
  the same DR in two "books" the app's P&L for that name is meaningless.

## Caveats

Yahoo Finance, end of day, nothing intraday. The 14-stock universe is the
stocks that happen to have Thai DRs, which is hindsight. Two months is not a
track record. This is my money and my rules. Don't copy them.

MIT license.
