"""SQLite persistence for funding snapshots and ticker stats."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from funding_bot.exchanges.binance import FundingSnapshot, TickerSnapshot


SCHEMA = """
CREATE TABLE IF NOT EXISTS funding_snapshots (
    symbol TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    funding_rate REAL NOT NULL,
    mark_price REAL NOT NULL,
    next_funding_utc TEXT,
    PRIMARY KEY (symbol, timestamp_utc)
);

CREATE INDEX IF NOT EXISTS idx_funding_symbol_time
    ON funding_snapshots (symbol, timestamp_utc DESC);

CREATE TABLE IF NOT EXISTS ticker_snapshots (
    symbol TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    last_price REAL NOT NULL,
    quote_volume_24h REAL NOT NULL,
    PRIMARY KEY (symbol, timestamp_utc)
);
"""


class Database:
    """Thin sqlite3 wrapper specialised for the bot's needs."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
        finally:
            conn.close()

    def insert_funding(self, snapshots: Iterable[FundingSnapshot]) -> int:
        rows = [
            (
                s.symbol,
                s.timestamp.astimezone(timezone.utc).isoformat(),
                s.funding_rate,
                s.mark_price,
                s.next_funding_time.astimezone(timezone.utc).isoformat()
                if s.next_funding_time
                else None,
            )
            for s in snapshots
        ]
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO funding_snapshots
                    (symbol, timestamp_utc, funding_rate, mark_price, next_funding_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def insert_tickers(self, tickers: Iterable[TickerSnapshot]) -> int:
        rows = [
            (
                t.symbol,
                t.timestamp.astimezone(timezone.utc).isoformat(),
                t.last_price,
                t.quote_volume_24h,
            )
            for t in tickers
        ]
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO ticker_snapshots
                    (symbol, timestamp_utc, last_price, quote_volume_24h)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def latest_funding(self, symbol: str) -> FundingSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT symbol, timestamp_utc, funding_rate, mark_price, next_funding_utc
                FROM funding_snapshots
                WHERE symbol = ?
                ORDER BY timestamp_utc DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()
        if row is None:
            return None
        return FundingSnapshot(
            symbol=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            funding_rate=row[2],
            mark_price=row[3],
            next_funding_time=datetime.fromisoformat(row[4]) if row[4] else None,
        )

    def count_funding_rows(self) -> int:
        with self._connect() as conn:
            (count,) = conn.execute("SELECT COUNT(*) FROM funding_snapshots").fetchone()
        return count
