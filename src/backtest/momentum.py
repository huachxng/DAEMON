"""Top-N cross-sectional momentum with optional trend filter.

Once a month (first trading day), rank the universe by trailing return and
hold the top N equal-weight. Anything not picked gets weight 0 (cash — we
never short). Optional filters:
- sma_filter: only allow names trading above their own N-day average
- min_momentum: only allow names whose trailing return clears a bar
"""


class TopNMomentum:
    def __init__(self, n=5, lookback=126, sma_filter=200, min_momentum=0.0,
                 rebalance_every=1):
        self.n = n
        self.lookback = lookback
        self.sma_filter = sma_filter
        self.min_momentum = min_momentum
        self.rebalance_every = rebalance_every  # in months
        self._boundaries_seen = 0

    def target_weights(self, closes):
        if len(closes) < 2 or closes.index[-1].month == closes.index[-2].month:
            return None  # act only on the first trading day of a new month
        self._boundaries_seen += 1
        if (self._boundaries_seen - 1) % self.rebalance_every != 0:
            return None  # e.g. rebalance_every=3 -> act on every 3rd boundary
        return self.select(closes)

    def select(self, closes):
        """Top-N as weights, without the calendar gate (used for bootstrap)."""
        ranking = self.ranked(closes)
        if ranking is None:
            return None
        winners = ranking[: self.n]
        weight = 1.0 / self.n
        return {t: (weight if t in winners else 0.0) for t in closes.columns}

    def ranked(self, closes):
        """Full ordered ranking (best momentum first) after all filters."""
        need = self.lookback + 1
        if self.sma_filter:
            need = max(need, self.sma_filter)
        if len(closes) < need:
            return None

        scores = {}
        for ticker in closes.columns:
            series = closes[ticker].dropna()
            if len(series) < need:
                continue
            momentum = series.iloc[-1] / series.iloc[-1 - self.lookback] - 1.0
            if momentum < self.min_momentum:
                continue
            if self.sma_filter and series.iloc[-1] < series.tail(self.sma_filter).mean():
                continue
            scores[ticker] = momentum

        return sorted(scores, key=scores.get, reverse=True)


def is_repick_due(last_repick_iso, today_iso, every_months: int) -> bool:
    """Quarterly means >= every_months calendar months since the last pick.
    Stateless on purpose — the caller persists last_repick_iso; the old
    per-instance counter re-picked every month (bug found 2026-08-19)."""
    if last_repick_iso is None:
        return True
    ly, lm = int(last_repick_iso[:4]), int(last_repick_iso[5:7])
    ty, tm = int(today_iso[:4]), int(today_iso[5:7])
    return (ty - ly) * 12 + (tm - lm) >= every_months
