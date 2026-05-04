"""Historical data loading for backtests.

Two options:
  * `download` — pulls funding history from Binance and stores it in the
    project's SQLite DB.
  * `replay_from_db` — yields historical snapshots in chronological order
    so the backtest runner can step through them.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator

from loguru import logger

from funding_bot.exchanges.binance import BinanceClient, FundingSnapshot, TickerSnapshot


@dataclass(frozen=True)
class HistoricalSnapshot:
    """A funding print at a specific historical instant for one symbol."""

    symbol: str
    timestamp: datetime
    funding_rate: float
    mark_price: float


def _to_funding(snap: HistoricalSnapshot, *, next_funding: datetime) -> FundingSnapshot:
    return FundingSnapshot(
        symbol=snap.symbol,
        funding_rate=snap.funding_rate,
        next_funding_time=next_funding,
        mark_price=snap.mark_price,
        timestamp=snap.timestamp,
    )


class HistoricalLoader:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS funding_snapshots (
                    symbol TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    funding_rate REAL NOT NULL,
                    mark_price REAL NOT NULL,
                    next_funding_utc TEXT,
                    PRIMARY KEY (symbol, timestamp_utc)
                )
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
        finally:
            conn.close()

    def download(
        self,
        client: BinanceClient,
        symbols: list[str],
        *,
        days: int = 90,
    ) -> int:
        """Pull funding-rate history for each symbol and persist it."""
        since = datetime.now(tz=timezone.utc) - timedelta(days=days)
        since_ms = int(since.timestamp() * 1000)
        total = 0
        for symbol in symbols:
            try:
                history = client.fetch_funding_history(
                    symbol, since_ms=since_ms, limit=1000
                )
            except Exception as exc:  # pragma: no cover - network noise
                logger.warning("Skipping {} due to error: {}", symbol, exc)
                continue
            rows = [
                (
                    s.symbol,
                    s.timestamp.astimezone(timezone.utc).isoformat(),
                    s.funding_rate,
                    s.mark_price,
                    None,
                )
                for s in history
            ]
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO funding_snapshots
                        (symbol, timestamp_utc, funding_rate, mark_price, next_funding_utc)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            total += len(rows)
            logger.info("Downloaded {} prints for {}", len(rows), symbol)
        return total

    def insert(self, snapshots: Iterable[HistoricalSnapshot]) -> int:
        rows = [
            (
                s.symbol,
                s.timestamp.astimezone(timezone.utc).isoformat(),
                s.funding_rate,
                s.mark_price,
                None,
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

    def symbols(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT symbol FROM funding_snapshots ORDER BY symbol"
            ).fetchall()
        return [r[0] for r in rows]

    def replay(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        symbols: list[str] | None = None,
    ) -> Iterator[tuple[datetime, list[HistoricalSnapshot]]]:
        """Yield (timestamp, snapshots-at-this-instant) tuples in order.

        Snapshots are grouped by their funding-print timestamp, which on
        Binance lands every 8 hours at 00:00, 08:00 and 16:00 UTC.
        """
        clauses = []
        params: list = []
        if start is not None:
            clauses.append("timestamp_utc >= ?")
            params.append(start.astimezone(timezone.utc).isoformat())
        if end is not None:
            clauses.append("timestamp_utc < ?")
            params.append(end.astimezone(timezone.utc).isoformat())
        if symbols:
            clauses.append("symbol IN (" + ",".join("?" for _ in symbols) + ")")
            params.extend(symbols)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        query = (
            "SELECT symbol, timestamp_utc, funding_rate, mark_price "
            f"FROM funding_snapshots {where} "
            "ORDER BY timestamp_utc ASC"
        )
        with self._connect() as conn:
            cursor = conn.execute(query, params)
            current_ts: datetime | None = None
            bucket: list[HistoricalSnapshot] = []
            for symbol, ts_str, rate, price in cursor:
                ts = datetime.fromisoformat(ts_str)
                if current_ts is None:
                    current_ts = ts
                if ts != current_ts:
                    yield current_ts, bucket
                    bucket = []
                    current_ts = ts
                bucket.append(
                    HistoricalSnapshot(
                        symbol=symbol,
                        timestamp=ts,
                        funding_rate=rate,
                        mark_price=price,
                    )
                )
            if bucket and current_ts is not None:
                yield current_ts, bucket
