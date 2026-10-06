# Trading Rules Spec (paper book)

Every strategy the paperbot runs must be declared here and in config before it
trades. No mid-run improvisation. Status: ACTIVE as of 2026-08-14 (provisional — user grades weekly).

## Go-live configuration (paper book, ฿200k)
- **US sleeve (50%)**: TopNMomentum n=5, lookback 126d, SMA200 filter, monthly
  rebalance, on the 20-name US watchlist. Backtest: beat survivorship-matched
  equal-weight control 563% vs 269% over 5y (absolute level inflated; relative
  signal real). Fills next-open +10bps slippage, US paper fees.
- **Thai sleeve (50%)**: hold TDEX.BK (SET50 ETF) — the null strategy. SET
  momentum FAILED its backtest (37.1% quarterly / 32.8% monthly vs 49.4%
  buy-and-hold; Thai min-fees are brutal at ฿200k scale). No active Thai
  strategy until one beats the index after fees.
- 10% cash buffer target; 15% per-name cap; circuit breaker overrides all.

## Position sizing (all strategies)
- Volatility-targeted sizing; max 15% of book equity per name
- Min 10% cash buffer
- Circuit breaker overrides everything: halt buys ≤ ฿160k, liquidate ≤ ฿155k

## Candidate strategies (to be backtested in Phase 3)
1. **SET trend + momentum** — SMA trend filter + cross-sectional momentum ranking on liquid SET names
2. **US large-cap momentum** — 3–12 month momentum with monthly rebalance
3. **Covered-call overlay (US, later)** — only after IV snapshot history matures

Backtest acceptance bar (before live-on-paper): beats buy-and-hold benchmark
after fees on ≥5 years of data, max drawdown compatible with the 150k floor,
and results reported with fees on vs off.

## LIVE sleeve (real money, user-executed) — ACTIVE 2026-08-14
User directive: daemon generates orders from its own analysis with a clean
฿200,000; user executes every ticket in Streaming; user's personal positions
are not managed (report-only). Universe: TDEX.BK + verified SET DRs (dr_map).
Signals ranked on US underlyings (5y data), tickets written on the DRs.
Friction backtest gate PASSED: quarterly top-5 momentum, real BLS fee
0.2215%/side + min ฿50 + 25bps slippage → 567% vs 264% equal-weight control
(5y, survivorship-matched; absolute levels inflated, relative edge real).
Deployment capped at 70% (TDEX 25% + momentum 45% + 30% cash) because the
strategy's historical 29% maxDD from full deployment would pierce the ฿150k
floor. Breaker ladder unchanged; liquidation emits SELL tickets + urgent push.

## Risk dial 80% + graduated floor defence — 2026-08-23 (user directive)
Sleeves: momentum 55% (5 × 11%) + TDEX 25%, cash ~20%. Breaker ladder now
ACTIVE at the first rung: equity ≤ ฿160k halves every target (SELL tickets
issued, buys suppressed); ≤ ฿155k liquidates all. Min ticket ฿3,000 both sides
(dust lesson, graded F). Command hub = Gmail thread "[CLAUDE TRADE]": the daemon
posts orders there, the user replies with fills, both daily runs read and log.
LINE bot deferred to the day-60 review.

## Top-3 concentration — 2026-08-23 (user choice, evidence-based)
User target: +10–30% on ฿200k by 2026-10-13; "too slow, mindful of fees".
Friction backtest (THB, 0.2215%/side, 25bps), 80% deployed:
  top-5+TDEX 25.2% CAGR / worst ฿160k · top-3+TDEX 30.8% / ฿157k (64 trades vs 95)
  top-5+NDX 27.9% / ฿157k · top-3+NDX 33.4% / ฿155k (= liquidation line → rejected)
Chosen: top-3 + TDEX. Slots 55%/3 ≈ 18% each; max_position_pct 20. Honest 7-week
expectation ≈ +3.7%; the target needs a strong quarter. No extra trading to chase —
monthly rotation lost to quarterly in every backtest. Weekly review: Sunday 19:00 BKK
in the hub thread; user grades decisions A–F.
