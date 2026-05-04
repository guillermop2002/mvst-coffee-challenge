"""Tests for the Portfolio model."""

from datetime import datetime, timezone

import pytest

from funding_bot.strategy.portfolio import Portfolio, make_position


TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _pos(symbol: str = "BTC/USDT:USDT", notional: float = 3000.0, rate: float = 0.0001):
    return make_position(
        symbol=symbol,
        notional_per_leg=notional,
        spot_capital=notional,
        short_margin=notional / 3,
        entry_funding_rate=rate,
        entry_price=50_000.0,
        now=TS,
    )


def test_open_uses_capital() -> None:
    pf = Portfolio(capital_total=10_000)
    pf.open(_pos())
    # 3000 spot + 1000 margin
    assert pf.capital_used == pytest.approx(4000)
    assert pf.capital_available == pytest.approx(6000)
    assert pf.n_open == 1


def test_cannot_double_open() -> None:
    pf = Portfolio(capital_total=10_000)
    pf.open(_pos())
    with pytest.raises(ValueError):
        pf.open(_pos())


def test_insufficient_capital_raises() -> None:
    pf = Portfolio(capital_total=1_000)
    with pytest.raises(ValueError, match="Insufficient capital"):
        pf.open(_pos(notional=3_000))


def test_collect_funding_increases_pnl() -> None:
    pf = Portfolio(capital_total=10_000)
    pf.open(_pos())
    pos = pf.get("BTC/USDT:USDT")
    assert pos is not None
    pos.collect_funding(funding_rate=0.0001, mark_price=50_000.0)
    # 3000 * 0.0001 = $0.30
    assert pos.funding_collected_usd == pytest.approx(0.30)
    assert pf.total_funding_collected == pytest.approx(0.30)


def test_close_realises_funding() -> None:
    pf = Portfolio(capital_total=10_000)
    pf.open(_pos())
    pos = pf.get("BTC/USDT:USDT")
    assert pos is not None
    for _ in range(10):
        pos.collect_funding(funding_rate=0.0001, mark_price=50_000.0)
    closed = pf.close("BTC/USDT:USDT")
    assert closed.symbol == "BTC/USDT:USDT"
    assert pf.realized_pnl == pytest.approx(3.0)
    assert pf.n_open == 0
    assert pf.equity == pytest.approx(10_003.0)


def test_worst_apy_picks_lowest() -> None:
    pf = Portfolio(capital_total=10_000)
    pf.open(_pos(symbol="A", rate=0.0003))
    pf.open(_pos(symbol="B", rate=0.0001))
    result = pf.worst_apy()
    assert result is not None
    assert result[0] == "B"
