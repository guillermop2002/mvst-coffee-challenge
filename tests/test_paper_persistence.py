"""Tests for paper portfolio + event persistence."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from funding_bot.paper.executor import ExecutionEvent
from funding_bot.paper.persistence import PaperStore
from funding_bot.strategy.portfolio import Portfolio, make_position


TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path: Path) -> PaperStore:
    return PaperStore(tmp_path / "paper.db")


def test_session_creation_is_idempotent(store: PaperStore) -> None:
    first = store.get_or_create_session(10_000)
    second = store.get_or_create_session(10_000)
    assert first == second


def test_save_and_load_portfolio(store: PaperStore) -> None:
    session_id = store.get_or_create_session(10_000)
    pf = Portfolio(capital_total=10_000, realized_pnl=12.34)
    pf.open(
        make_position(
            symbol="BTC/USDT:USDT",
            notional_per_leg=3000,
            spot_capital=3000,
            short_margin=1000,
            entry_funding_rate=0.0005,
            entry_price=50_000.0,
            now=TS,
        )
    )
    pf.positions["BTC/USDT:USDT"].funding_collected_usd = 5.0
    store.save_portfolio(session_id, pf)

    loaded = store.load_portfolio(session_id)
    assert loaded is not None
    assert loaded.realized_pnl == pytest.approx(12.34)
    assert loaded.n_open == 1
    pos = loaded.positions["BTC/USDT:USDT"]
    assert pos.notional_per_leg == 3000
    assert pos.funding_collected_usd == 5.0


def test_save_replaces_previous_positions(store: PaperStore) -> None:
    session_id = store.get_or_create_session(10_000)
    pf = Portfolio(capital_total=10_000)
    pf.open(
        make_position(
            symbol="A",
            notional_per_leg=1000,
            spot_capital=1000,
            short_margin=333,
            entry_funding_rate=0.0001,
            entry_price=100,
            now=TS,
        )
    )
    store.save_portfolio(session_id, pf)

    pf.close("A")
    pf.open(
        make_position(
            symbol="B",
            notional_per_leg=1000,
            spot_capital=1000,
            short_margin=333,
            entry_funding_rate=0.0002,
            entry_price=100,
            now=TS,
        )
    )
    store.save_portfolio(session_id, pf)

    loaded = store.load_portfolio(session_id)
    assert loaded is not None
    assert set(loaded.positions.keys()) == {"B"}


def test_event_log_append_and_recent(store: PaperStore) -> None:
    session_id = store.get_or_create_session(10_000)
    events = [
        ExecutionEvent(
            timestamp=TS,
            action="OPEN",
            symbol="BTC/USDT:USDT",
            detail="test",
            pnl_delta=-1.0,
        ),
        ExecutionEvent(
            timestamp=TS,
            action="FUNDING",
            symbol="BTC/USDT:USDT",
            detail="rate=0.01%",
            pnl_delta=0.30,
        ),
    ]
    store.append_events(session_id, events)
    recent = store.recent_events(session_id, limit=10)
    assert len(recent) == 2
    actions = {e.action for e in recent}
    assert actions == {"OPEN", "FUNDING"}


def test_reset_clears_everything(store: PaperStore) -> None:
    session_id = store.get_or_create_session(10_000)
    store.append_events(
        session_id,
        [ExecutionEvent(timestamp=TS, action="OPEN", symbol="A", detail="", pnl_delta=0)],
    )
    store.reset()
    assert store.recent_events(session_id) == []
    assert store.load_portfolio(session_id) is None
