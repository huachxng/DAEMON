"""Pull EOD data from Yahoo Finance into the store.

Free data, honestly labeled: EOD/delayed, one pull per run. First pull per
symbol goes 5 years deep (for backtests); later pulls are incremental.
"""
import yfinance as yf

from src.config import load_universe, all_yahoo_symbols


def _normalize(history_df):
    """yfinance history -> our bars: date/open/high/low/close/adj_close/volume."""
    df = history_df.reset_index()
    df["date"] = df["Date"].dt.strftime("%Y-%m-%d")
    out = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Adj Close": "adj_close", "Volume": "volume",
    })
    if "adj_close" not in out.columns:      # auto_adjust quirk
        out["adj_close"] = out["close"]
    out["volume"] = out["volume"].fillna(0)
    # A bar without a close is an in-progress session (extended DR trading
    # publishes today's row with close=NaN until the session ends). Not EOD yet.
    out = out.dropna(subset=["close"])
    return out[["date", "open", "high", "low", "close", "adj_close", "volume"]]


def update_all(store, deep: bool = False) -> dict:
    """Fetch every universe symbol. Returns {symbol: summary_string}."""
    symbols = all_yahoo_symbols(load_universe())
    results = {}
    for sym, info in symbols.items():
        period = "5y" if (deep or store.last_price_date(sym) is None) else "1mo"
        try:
            tkr = yf.Ticker(sym)
            hist = tkr.history(period=period, auto_adjust=False)
            if hist.empty:
                results[sym] = "NO DATA"
                continue
            bars = _normalize(hist)
            store.upsert_prices(sym, bars)
            if info["kind"] == "fx":
                store.upsert_fx(zip(bars["date"], bars["close"]))
            if info["kind"] == "dr":
                divs = tkr.dividends
                if divs is not None and len(divs):
                    store.upsert_dividends(
                        sym,
                        [(d.strftime("%Y-%m-%d"), None, float(v))
                         for d, v in divs.items()],
                    )
            results[sym] = f"{len(bars)} bars to {bars['date'].iloc[-1]}"
        except Exception as e:
            results[sym] = f"ERROR: {type(e).__name__}: {e}"
    return results
