"""Tests for the SQLite storage layer."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from funding_bot.exchanges.binance import FundingSnapshot, TickerSnapshot
from funding_bot.storage import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def _snap(symbol: str, rate: float, ts: datetime) -> FundingSnapshot:
    return FundingSnapshot(
        symbol=symbol,
        funding_rate=rate,
        next_funding_time=None,
        mark_price=100.0,
        timestamp=ts,
    )


def test_insert_and_count(db: Database) -> None:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.insert_funding(
        [
            _snap("BTC/USDT:USDT", 0.0001, ts),
            _snap("ETH/USDT:USDT", 0.0002, ts),
        ]
    )
    assert db.count_funding_rows() == 2


def test_replace_on_duplicate(db: Database) -> None:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.insert_funding([_snap("BTC/USDT:USDT", 0.0001, ts)])
    db.insert_funding([_snap("BTC/USDT:USDT", 0.0003, ts)])
    assert db.count_funding_rows() == 1
    latest = db.latest_funding("BTC/USDT:USDT")
    assert latest is not None
    assert latest.funding_rate == 0.0003


def test_latest_returns_most_recent(db: Database) -> None:
    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later = datetime(2026, 1, 2, tzinfo=timezone.utc)
    db.insert_funding(
        [
            _snap("BTC/USDT:USDT", 0.0001, earlier),
            _snap("BTC/USDT:USDT", 0.0005, later),
        ]
    )
    latest = db.latest_funding("BTC/USDT:USDT")
    assert latest is not None
    assert latest.funding_rate == 0.0005


def test_latest_missing_symbol(db: Database) -> None:
    assert db.latest_funding("DOGE/USDT:USDT") is None


def test_insert_tickers(db: Database) -> None:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    n = db.insert_tickers(
        [
            TickerSnapshot("BTC/USDT:USDT", 50_000.0, 1_000_000_000.0, ts),
            TickerSnapshot("ETH/USDT:USDT", 3_000.0, 500_000_000.0, ts),
        ]
    )
    assert n == 2
