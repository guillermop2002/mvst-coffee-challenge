"""End-to-end tests for the StrategyEngine."""

from datetime import datetime, timezone

from funding_bot.config import StrategyConfig
from funding_bot.exchanges.binance import FundingSnapshot, TickerSnapshot
from funding_bot.strategy.decisions import (
    ClosePosition,
    HoldPosition,
    OpenPosition,
)
from funding_bot.strategy.engine import StrategyEngine
from funding_bot.strategy.portfolio import Portfolio, make_position
from funding_bot.strategy.scoring import score_opportunities


TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _funding(symbol: str, rate: float) -> FundingSnapshot:
    return FundingSnapshot(
        symbol=symbol,
        funding_rate=rate,
        next_funding_time=None,
        mark_price=100.0,
        timestamp=TS,
    )


def _ticker(symbol: str, volume: float = 100_000_000) -> TickerSnapshot:
    return TickerSnapshot(
        symbol=symbol,
        last_price=100.0,
        quote_volume_24h=volume,
        timestamp=TS,
    )


def _config(**overrides) -> StrategyConfig:
    base = dict(
        capital_usd=10_000,
        max_concurrent_positions=3,
        max_leverage=3.0,
        min_apy_threshold=12.0,
        rotation_hysteresis=0.30,
        kelly_fraction=0.20,
        max_position_pct=0.40,
    )
    base.update(overrides)
    return StrategyConfig(**base)


def test_empty_portfolio_opens_top_opportunities() -> None:
    funding = [
        _funding("A", 0.0005),  # 54.75% APY
        _funding("B", 0.0003),  # 32.85%
        _funding("C", 0.0002),  # 21.9%
        _funding("D", 0.0001),  # 10.95% (below threshold)
    ]
    tickers = {s.symbol: _ticker(s.symbol) for s in funding}
    opps = score_opportunities(funding, tickers)

    pf = Portfolio(capital_total=10_000)
    engine = StrategyEngine(_config())
    decisions = engine.decide(opportunities=opps, portfolio=pf)

    opens = [d for d in decisions if isinstance(d, OpenPosition)]
    assert {d.symbol for d in opens} == {"A", "B", "C"}
    # Capital was distributed across 3 positions, capped by 40% rule.
    for d in opens:
        assert d.sizing.notional_per_leg > 0


def test_position_below_threshold_closed() -> None:
    funding = [_funding("A", 0.00005)]  # 5.475% APY < 12% threshold
    tickers = {"A": _ticker("A")}
    opps = score_opportunities(funding, tickers)

    pf = Portfolio(capital_total=10_000)
    pf.open(
        make_position(
            symbol="A",
            notional_per_leg=3000,
            spot_capital=3000,
            short_margin=1000,
            entry_funding_rate=0.0005,
            entry_price=100,
            now=TS,
        )
    )
    engine = StrategyEngine(_config())
    decisions = engine.decide(opportunities=opps, portfolio=pf)

    closes = [d for d in decisions if isinstance(d, ClosePosition)]
    assert any(c.symbol == "A" for c in closes)


def test_held_position_above_threshold_is_held() -> None:
    funding = [_funding("A", 0.0005)]  # 54.75% APY
    tickers = {"A": _ticker("A")}
    opps = score_opportunities(funding, tickers)

    pf = Portfolio(capital_total=10_000)
    pos = make_position(
        symbol="A",
        notional_per_leg=3000,
        spot_capital=3000,
        short_margin=1000,
        entry_funding_rate=0.0005,
        entry_price=100,
        now=TS,
    )
    pf.open(pos)
    engine = StrategyEngine(_config())
    decisions = engine.decide(opportunities=opps, portfolio=pf)

    holds = [d for d in decisions if isinstance(d, HoldPosition)]
    assert any(h.symbol == "A" for h in holds)


def test_rotation_when_better_opportunity_appears() -> None:
    # Held: A at 15% APY. New candidate B at 50% APY.
    # 50% > 15% * 1.30 = 19.5%, so rotation should trigger.
    funding = [_funding("A", 0.000137), _funding("B", 0.000457)]
    tickers = {s.symbol: _ticker(s.symbol) for s in funding}
    opps = score_opportunities(funding, tickers)

    pf = Portfolio(capital_total=10_000)
    pf.open(
        make_position(
            symbol="A",
            notional_per_leg=3000,
            spot_capital=3000,
            short_margin=1000,
            entry_funding_rate=0.000137,
            entry_price=100,
            now=TS,
        )
    )
    engine = StrategyEngine(_config(max_concurrent_positions=1))
    decisions = engine.decide(opportunities=opps, portfolio=pf)

    closes = {d.symbol for d in decisions if isinstance(d, ClosePosition)}
    opens = {d.symbol for d in decisions if isinstance(d, OpenPosition)}
    assert "A" in closes
    assert "B" in opens


def test_no_rotation_within_hysteresis_band() -> None:
    # Held A at 30% APY, new candidate B at 33% APY.
    # 33% < 30% * 1.30 = 39%, so no rotation.
    funding = [_funding("A", 0.000274), _funding("B", 0.000302)]
    tickers = {s.symbol: _ticker(s.symbol) for s in funding}
    opps = score_opportunities(funding, tickers)

    pf = Portfolio(capital_total=10_000)
    pf.open(
        make_position(
            symbol="A",
            notional_per_leg=3000,
            spot_capital=3000,
            short_margin=1000,
            entry_funding_rate=0.000274,
            entry_price=100,
            now=TS,
        )
    )
    engine = StrategyEngine(_config(max_concurrent_positions=1))
    decisions = engine.decide(opportunities=opps, portfolio=pf)

    holds = {d.symbol for d in decisions if isinstance(d, HoldPosition)}
    closes = {d.symbol for d in decisions if isinstance(d, ClosePosition)}
    assert "A" in holds
    assert "A" not in closes
    # B may or may not be opened depending on free slots; with max=1, no slots free.
    opens = [d for d in decisions if isinstance(d, OpenPosition)]
    assert opens == []


def test_full_portfolio_no_open() -> None:
    funding = [
        _funding("A", 0.0005),
        _funding("B", 0.0005),
        _funding("C", 0.0005),
        _funding("D", 0.0005),
    ]
    tickers = {s.symbol: _ticker(s.symbol) for s in funding}
    opps = score_opportunities(funding, tickers)

    pf = Portfolio(capital_total=10_000)
    for sym in ("A", "B", "C"):
        pf.open(
            make_position(
                symbol=sym,
                notional_per_leg=2_000,
                spot_capital=2_000,
                short_margin=666,
                entry_funding_rate=0.0005,
                entry_price=100,
                now=TS,
            )
        )

    engine = StrategyEngine(_config())
    decisions = engine.decide(opportunities=opps, portfolio=pf)
    opens = [d for d in decisions if isinstance(d, OpenPosition)]
    # All slots are full and all held APYs are equal to the candidate's, so
    # no rotation triggers.
    assert opens == []
