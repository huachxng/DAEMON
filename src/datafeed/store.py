"""SQLite storage — the single source of truth for market data and bookkeeping.

One class, one file, no ORM: plain SQL kept readable on purpose.
"""
import sqlite3
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker    TEXT NOT NULL,
    date      TEXT NOT NULL,          -- ISO date, exchange-local trading day
    open REAL, high REAL, low REAL, close REAL, adj_close REAL,
    volume    INTEGER,
    PRIMARY KEY (ticker, date)
);
CREATE TABLE IF NOT EXISTS fx (
    date TEXT PRIMARY KEY,
    thb_usd REAL                       -- THB per 1 USD
);
CREATE TABLE IF NOT EXISTS trades (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    book   TEXT NOT NULL,              -- 'real' or 'paper'
    ticker TEXT NOT NULL,
    side   TEXT NOT NULL,              -- 'BUY' or 'SELL'
    qty    REAL NOT NULL,
    price  REAL NOT NULL,
    fees   REAL NOT NULL DEFAULT 0,
    ts     TEXT NOT NULL,              -- ISO datetime
    note   TEXT
);
CREATE TABLE IF NOT EXISTS dividends (
    ticker  TEXT NOT NULL,
    ex_date TEXT NOT NULL,
    pay_date TEXT,
    amount  REAL NOT NULL,             -- per share, gross
    wht     REAL NOT NULL DEFAULT 0.10,
    PRIMARY KEY (ticker, ex_date)
);
CREATE TABLE IF NOT EXISTS options_snapshots (
    ticker TEXT NOT NULL, date TEXT NOT NULL, expiry TEXT NOT NULL,
    strike REAL NOT NULL, type TEXT NOT NULL,   -- 'C' or 'P'
    bid REAL, ask REAL, iv REAL, oi INTEGER,
    PRIMARY KEY (ticker, date, expiry, strike, type)
);
CREATE TABLE IF NOT EXISTS pending_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    created_ts TEXT NOT NULL,
    after_date TEXT,                   -- fill only with a bar strictly newer than this
    filled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    book TEXT NOT NULL,
    action TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    rule_id TEXT,
    outcome_grade TEXT                  -- filled in later by the user's grading
);
CREATE TABLE IF NOT EXISTS order_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    book TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL,                        -- limit/fill price if known
    event TEXT NOT NULL,               -- ticket_issued | placed_at_broker | filled | cancelled
    note TEXT
);
CREATE TABLE IF NOT EXISTS equity_snapshots (
    date TEXT NOT NULL,
    book TEXT NOT NULL,
    equity REAL NOT NULL,
    PRIMARY KEY (date, book)
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    message_en TEXT NOT NULL,
    message_th TEXT NOT NULL,
    delivered_via TEXT
);
"""


class Store:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SCHEMA)

    def upsert_prices(self, ticker: str, bars: pd.DataFrame) -> None:
        """Insert or update EOD bars. Re-running with the same data is safe."""
        rows = [
            (ticker, str(r["date"]), r["open"], r["high"], r["low"],
             r["close"], r["adj_close"], int(r["volume"]))
            for _, r in bars.iterrows()
        ]
        self.conn.executemany(
            """INSERT INTO prices (ticker, date, open, high, low, close, adj_close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker, date) DO UPDATE SET
                 open=excluded.open, high=excluded.high, low=excluded.low,
                 close=excluded.close, adj_close=excluded.adj_close,
                 volume=excluded.volume""",
            rows,
        )
        self.conn.commit()

    def insert_trade(self, book, ticker, side, qty, price, fees, ts, note=""):
        self.conn.execute(
            "INSERT INTO trades (book, ticker, side, qty, price, fees, ts, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (book, ticker, side, qty, price, fees, ts, note),
        )
        self.conn.commit()

    def read_trades(self, book: str) -> list:
        from src.portfolio.ledger import Trade

        rows = self.conn.execute(
            "SELECT book, ticker, side, qty, price, fees, ts, COALESCE(note, '') "
            "FROM trades WHERE book = ? ORDER BY ts, id",
            (book,),
        ).fetchall()
        return [Trade(*row) for row in rows]

    def upsert_fx(self, pairs) -> None:
        """pairs: iterable of (iso_date, thb_per_usd)."""
        self.conn.executemany(
            "INSERT INTO fx (date, thb_usd) VALUES (?, ?) "
            "ON CONFLICT(date) DO UPDATE SET thb_usd=excluded.thb_usd",
            list(pairs),
        )
        self.conn.commit()

    def read_fx(self) -> dict:
        return dict(self.conn.execute("SELECT date, thb_usd FROM fx ORDER BY date"))

    def latest_fx(self) -> float:
        row = self.conn.execute(
            "SELECT thb_usd FROM fx ORDER BY date DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def upsert_dividends(self, ticker, rows) -> None:
        """rows: iterable of (ex_date, pay_date, amount_per_share)."""
        self.conn.executemany(
            "INSERT INTO dividends (ticker, ex_date, pay_date, amount) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(ticker, ex_date) DO UPDATE SET "
            "pay_date=excluded.pay_date, amount=excluded.amount",
            [(ticker, ex, pay, amt) for ex, pay, amt in rows],
        )
        self.conn.commit()

    def read_dividends(self, ticker: str) -> list:
        rows = self.conn.execute(
            "SELECT ex_date, pay_date, amount, wht FROM dividends "
            "WHERE ticker = ? ORDER BY ex_date",
            (ticker,),
        ).fetchall()
        return [
            {"ex_date": ex, "pay_date": pay, "amount": amt, "wht": wht}
            for ex, pay, amt, wht in rows
        ]

    def insert_pending_order(self, book, ticker, side, qty, created_ts, after_date):
        self.conn.execute(
            "INSERT INTO pending_orders (book, ticker, side, qty, created_ts, after_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (book, ticker, side, qty, created_ts, after_date),
        )
        self.conn.commit()
        # Audit trail: a genuinely new/changed ticket gets an order event; the
        # daily cancel+reissue of an unchanged ticket does not spam the log.
        if self._last_ticket_qty(book, ticker, side) != qty:
            self.log_order_event(book, ticker, side, qty, None,
                                 "ticket_issued", ts=created_ts)

    def unfilled_orders(self, book: str) -> list:
        rows = self.conn.execute(
            "SELECT id, ticker, side, qty, created_ts, after_date FROM pending_orders "
            "WHERE book = ? AND filled = 0 ORDER BY id",
            (book,),
        ).fetchall()
        return [dict(zip(("id", "ticker", "side", "qty", "created_ts", "after_date"), r))
                for r in rows]

    def cancel_unfilled(self, book: str):
        """Latest decision supersedes anything still queued (marks filled=-1)."""
        self.conn.execute(
            "UPDATE pending_orders SET filled = -1 WHERE book = ? AND filled = 0",
            (book,),
        )
        self.conn.commit()

    def mark_order_filled(self, order_id: int):
        self.conn.execute("UPDATE pending_orders SET filled = 1 WHERE id = ?", (order_id,))
        self.conn.commit()

    def insert_journal(self, ts, book, action, reasoning, rule_id=None):
        self.conn.execute(
            "INSERT INTO journal (ts, book, action, reasoning, rule_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, book, action, reasoning, rule_id),
        )
        self.conn.commit()

    def read_journal_tail(self, limit=20) -> list:
        rows = self.conn.execute(
            "SELECT id, ts, book, action, reasoning, rule_id, outcome_grade "
            "FROM journal ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            dict(zip(("id", "ts", "book", "action", "reasoning", "rule_id", "grade"), r))
            for r in rows
        ]

    def log_order_event(self, book, ticker, side, qty, price, event, ts, note=""):
        """Append-only audit trail of every order action. Never updated, never deleted."""
        self.conn.execute(
            "INSERT INTO order_events (ts, book, ticker, side, qty, price, event, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, book, ticker, side, qty, price, event, note),
        )
        self.conn.commit()

    def read_order_events(self, book=None) -> list:
        q = ("SELECT ts, book, ticker, side, qty, price, event, note FROM order_events "
             + ("WHERE book = ? " if book else "") + "ORDER BY ts, id")
        rows = self.conn.execute(q, (book,) if book else ()).fetchall()
        keys = ("ts", "book", "ticker", "side", "qty", "price", "event", "note")
        return [dict(zip(keys, r)) for r in rows]

    def _last_ticket_qty(self, book, ticker, side):
        row = self.conn.execute(
            "SELECT qty FROM order_events WHERE book=? AND ticker=? AND side=? "
            "AND event='ticket_issued' ORDER BY id DESC LIMIT 1",
            (book, ticker, side),
        ).fetchone()
        return row[0] if row else None

    def snapshot_equity(self, date, book, equity) -> None:
        self.conn.execute(
            "INSERT INTO equity_snapshots (date, book, equity) VALUES (?, ?, ?) "
            "ON CONFLICT(date, book) DO UPDATE SET equity=excluded.equity",
            (date, book, equity),
        )
        self.conn.commit()

    def read_equity_history(self, book) -> list:
        rows = self.conn.execute(
            "SELECT date, equity FROM equity_snapshots WHERE book=? ORDER BY date",
            (book,),
        ).fetchall()
        return [{"date": d, "equity": e} for d, e in rows]

    def set_state(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def get_state(self, key: str):
        row = self.conn.execute(
            "SELECT value FROM state WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def last_price_date(self, ticker: str):
        row = self.conn.execute(
            "SELECT MAX(date) FROM prices WHERE ticker = ?", (ticker,)
        ).fetchone()
        return row[0]

    def read_prices(self, ticker: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT date, open, high, low, close, adj_close, volume "
            "FROM prices WHERE ticker = ? ORDER BY date",
            self.conn,
            params=(ticker,),
        )
