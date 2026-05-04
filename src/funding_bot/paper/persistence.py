"""Persist paper-trading state and event log to SQLite.

Lets paper sessions resume across restarts. Events are append-only, so
the table doubles as a transaction log we can replay or audit later.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from funding_bot.paper.executor import ExecutionEvent
from funding_bot.strategy.portfolio import Portfolio, Position


SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_session (
    id INTEGER PRIMARY KEY,
    started_utc TEXT NOT NULL,
    capital_total REAL NOT NULL,
    realized_pnl REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS paper_positions (
    session_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    notional_per_leg REAL NOT NULL,
    spot_capital REAL NOT NULL,
    short_margin REAL NOT NULL,
    entry_funding_rate REAL NOT NULL,
    entry_apy REAL NOT NULL,
    entry_price REAL NOT NULL,
    opened_utc TEXT NOT NULL,
    funding_collected_usd REAL NOT NULL DEFAULT 0,
    last_funding_apy REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, symbol)
);

CREATE TABLE IF NOT EXISTS paper_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp_utc TEXT NOT NULL,
    action TEXT NOT NULL,
    symbol TEXT NOT NULL,
    detail TEXT,
    pnl_delta REAL NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_paper_events_session
    ON paper_events (session_id, timestamp_utc DESC);
"""


class PaperStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def get_or_create_session(self, capital_total: float) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM paper_session ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                return int(row[0])
            cur = conn.execute(
                """
                INSERT INTO paper_session (started_utc, capital_total, realized_pnl)
                VALUES (?, ?, 0)
                """,
                (datetime.now(tz=timezone.utc).isoformat(), capital_total),
            )
            return int(cur.lastrowid or 0)

    def reset(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM paper_events")
            conn.execute("DELETE FROM paper_positions")
            conn.execute("DELETE FROM paper_session")

    def save_portfolio(self, session_id: int, portfolio: Portfolio) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE paper_session SET realized_pnl = ? WHERE id = ?",
                (portfolio.realized_pnl, session_id),
            )
            conn.execute(
                "DELETE FROM paper_positions WHERE session_id = ?",
                (session_id,),
            )
            rows = [
                (
                    session_id,
                    p.symbol,
                    p.notional_per_leg,
                    p.spot_capital,
                    p.short_margin,
                    p.entry_funding_rate,
                    p.entry_apy,
                    p.entry_price,
                    p.opened_at.astimezone(timezone.utc).isoformat(),
                    p.funding_collected_usd,
                    p.last_funding_apy,
                )
                for p in portfolio.positions.values()
            ]
            conn.executemany(
                """
                INSERT INTO paper_positions
                    (session_id, symbol, notional_per_leg, spot_capital, short_margin,
                     entry_funding_rate, entry_apy, entry_price, opened_utc,
                     funding_collected_usd, last_funding_apy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def load_portfolio(self, session_id: int) -> Portfolio | None:
        with self._connect() as conn:
            session = conn.execute(
                "SELECT capital_total, realized_pnl FROM paper_session WHERE id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                return None
            capital_total, realized = session

            position_rows = conn.execute(
                """
                SELECT symbol, notional_per_leg, spot_capital, short_margin,
                       entry_funding_rate, entry_apy, entry_price, opened_utc,
                       funding_collected_usd, last_funding_apy
                FROM paper_positions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchall()

        portfolio = Portfolio(capital_total=capital_total, realized_pnl=realized)
        for row in position_rows:
            pos = Position(
                symbol=row[0],
                notional_per_leg=row[1],
                spot_capital=row[2],
                short_margin=row[3],
                entry_funding_rate=row[4],
                entry_apy=row[5],
                entry_price=row[6],
                opened_at=datetime.fromisoformat(row[7]),
                funding_collected_usd=row[8],
                last_funding_apy=row[9],
            )
            portfolio.positions[pos.symbol] = pos
        return portfolio

    def append_events(
        self, session_id: int, events: Iterable[ExecutionEvent]
    ) -> None:
        rows = [
            (
                session_id,
                e.timestamp.astimezone(timezone.utc).isoformat(),
                e.action,
                e.symbol,
                e.detail,
                e.pnl_delta,
            )
            for e in events
        ]
        if not rows:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO paper_events
                    (session_id, timestamp_utc, action, symbol, detail, pnl_delta)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def recent_events(self, session_id: int, limit: int = 50) -> list[ExecutionEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT timestamp_utc, action, symbol, detail, pnl_delta
                FROM paper_events
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            ExecutionEvent(
                timestamp=datetime.fromisoformat(row[0]),
                action=row[1],
                symbol=row[2],
                detail=row[3] or "",
                pnl_delta=row[4],
            )
            for row in rows
        ]
