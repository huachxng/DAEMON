
## 2026-08-23 — Never ticket dust (graded F by user)
The daemon issued SELL 100 AMZN06 (฿212 notional) as a drift trim; the user
executed it and realized −฿8.96. Total portfolio benefit: none. Rule, now in
code (`sizing.drop_dust`, tested): no ticket below ฿5,000 notional on either
side; only full exits (stop / rotation / breaker) are exempt. Every ticket must
be worth the user's attention and its fee.
