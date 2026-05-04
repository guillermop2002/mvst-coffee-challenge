"""Tests for the paper executor + fee model."""

from datetime import datetime, timezone

import pytest

from funding_bot.exchanges.binance import FundingSnapshot, TickerSnapshot
from funding_bot.paper.executor import FeeModel, PaperExecutor
from funding_bot.strategy.decisions import (
    ClosePosition,
    HoldPosition,
    OpenPosition,
)
from funding_bot.strategy.portfolio import Portfolio, make_position
from funding_bot.strategy.scoring import Opportunity
from funding_bot.strategy.sizing import SizingResult


TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _opp(symbol: str = "BTC/USDT:USDT", rate: float = 0.0005) -> Opportunity:
    funding = FundingSnapshot(
        symbol=symbol,
        funding_rate=rate,
        next_funding_time=None,
        mark_price=50_000.0,
        timestamp=TS,
    )
    ticker = TickerSnapshot(
        symbol=symbol,
        last_price=50_000.0,
        quote_volume_24h=100_000_000,
        timestamp=TS,
    )
    return Opportunity(funding=funding, ticker=ticker, score=funding.apy)


def _sizing(notional: float = 3000.0) -> SizingResult:
    return SizingResult(
        notional_per_leg=notional,
        spot_capital=notional,
        short_margin=notional / 3,
        capital_used=notional + notional / 3,
        leverage=3.0,
    )


def test_open_decision_creates_position_and_charges_fees() -> None:
    pf = Portfolio(capital_total=10_000)
    executor = PaperExecutor()
    decisions = [
        OpenPosition(
            opportunity=_opp(),
            sizing=_sizing(),
            reason="test",
        )
    ]
    result = executor.apply(
        portfolio=pf,
        decisions=decisions,
        prices={"BTC/USDT:USDT": 50_000.0},
        now=TS,
    )

    assert result.n_opens == 1
    assert pf.n_open == 1
    # Fee = (10 + 4 + 2*2) bps = 18 bps on $3000 = $5.40
    assert result.fees_paid == pytest.approx(5.40)
    assert pf.realized_pnl == pytest.approx(-5.40)


def test_open_skipped_when_capital_insufficient() -> None:
    pf = Portfolio(capital_total=1_000)
    executor = PaperExecutor()
    decisions = [
        OpenPosition(
            opportunity=_opp(),
            sizing=_sizing(notional=3000),
            reason="test",
        )
    ]
    result = executor.apply(
        portfolio=pf,
        decisions=decisions,
        prices={"BTC/USDT:USDT": 50_000.0},
        now=TS,
    )
    assert result.n_opens == 0
    assert pf.n_open == 0
    assert any(e.action == "OPEN_SKIPPED" for e in result.events)


def test_close_decision_removes_position_and_charges_fees() -> None:
    pf = Portfolio(capital_total=10_000)
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

    executor = PaperExecutor()
    decisions = [ClosePosition(symbol="BTC/USDT:USDT", reason="test", current_apy=5.0)]
    result = executor.apply(
        portfolio=pf,
        decisions=decisions,
        prices={"BTC/USDT:USDT": 51_000.0},
        now=TS,
    )

    assert result.n_closes == 1
    assert pf.n_open == 0
    assert result.fees_paid == pytest.approx(5.40)


def test_close_skipped_when_position_missing() -> None:
    pf = Portfolio(capital_total=10_000)
    executor = PaperExecutor()
    result = executor.apply(
        portfolio=pf,
        decisions=[ClosePosition(symbol="X", reason="t", current_apy=0)],
        prices={},
        now=TS,
    )
    assert result.n_closes == 0
    assert any(e.action == "CLOSE_SKIPPED" for e in result.events)


def test_hold_does_nothing() -> None:
    pf = Portfolio(capital_total=10_000)
    executor = PaperExecutor()
    result = executor.apply(
        portfolio=pf,
        decisions=[HoldPosition(symbol="X", current_apy=20)],
        prices={},
        now=TS,
    )
    assert result.events == []
    assert result.n_opens == 0
    assert result.n_closes == 0


def test_close_executes_before_open_to_free_capital() -> None:
    pf = Portfolio(capital_total=4_500)
    pf.open(
        make_position(
            symbol="OLD",
            notional_per_leg=3000,
            spot_capital=3000,
            short_margin=1000,
            entry_funding_rate=0.0001,
            entry_price=50_000.0,
            now=TS,
        )
    )
    # After opening OLD, capital_available = 4500 - 4000 = 500.
    # Without a CLOSE-before-OPEN, the second OPEN would fail.
    executor = PaperExecutor()
    decisions = [
        ClosePosition(symbol="OLD", reason="rotate", current_apy=10.95),
        OpenPosition(
            opportunity=_opp(symbol="NEW"),
            sizing=_sizing(notional=3000),
            reason="rotate",
        ),
    ]
    result = executor.apply(
        portfolio=pf,
        decisions=decisions,
        prices={"OLD": 50_000.0, "NEW": 50_000.0},
        now=TS,
    )
    assert result.n_closes == 1
    assert result.n_opens == 1
    assert "NEW" in pf.positions
    assert "OLD" not in pf.positions


def test_settle_funding_credits_position() -> None:
    pf = Portfolio(capital_total=10_000)
    pf.open(
        make_position(
            symbol="BTC/USDT:USDT",
            notional_per_leg=3000,
            spot_capital=3000,
            short_margin=1000,
            entry_funding_rate=0.0001,
            entry_price=50_000.0,
            now=TS,
        )
    )
    executor = PaperExecutor()
    result = executor.settle_funding(
        portfolio=pf,
        funding_by_symbol={"BTC/USDT:USDT": (0.0001, 51_000.0)},
        now=TS,
    )
    assert len(result.events) == 1
    # 3000 * 0.0001 = $0.30
    assert pf.positions["BTC/USDT:USDT"].funding_collected_usd == pytest.approx(0.30)


def test_fee_model_round_trip_zero_fees() -> None:
    fee = FeeModel(spot_taker_bps=0, futures_taker_bps=0, slippage_bps=0)
    assert fee.open_cost(1_000) == 0.0
    assert fee.close_cost(1_000) == 0.0
