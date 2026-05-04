"""Tests for opportunity scoring."""

from datetime import datetime, timezone

from funding_bot.exchanges.binance import FundingSnapshot, TickerSnapshot
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


def _ticker(symbol: str, volume: float) -> TickerSnapshot:
    return TickerSnapshot(
        symbol=symbol,
        last_price=100.0,
        quote_volume_24h=volume,
        timestamp=TS,
    )


def test_higher_apy_scores_higher() -> None:
    funding = [_funding("A", 0.0005), _funding("B", 0.0002)]
    tickers = {
        "A": _ticker("A", 100_000_000),
        "B": _ticker("B", 100_000_000),
    }
    opps = score_opportunities(funding, tickers)
    assert opps[0].symbol == "A"
    assert opps[0].score > opps[1].score


def test_negative_funding_excluded() -> None:
    funding = [_funding("A", -0.0005), _funding("B", 0.0001)]
    tickers = {
        "A": _ticker("A", 100_000_000),
        "B": _ticker("B", 100_000_000),
    }
    opps = score_opportunities(funding, tickers)
    assert {o.symbol for o in opps} == {"B"}


def test_low_volume_excluded() -> None:
    funding = [_funding("A", 0.0005), _funding("B", 0.0005)]
    tickers = {
        "A": _ticker("A", 1_000_000),
        "B": _ticker("B", 100_000_000),
    }
    opps = score_opportunities(funding, tickers, min_volume_usd=10_000_000)
    assert {o.symbol for o in opps} == {"B"}


def test_excluded_symbols_skipped() -> None:
    funding = [_funding("A", 0.0005), _funding("B", 0.0005)]
    tickers = {
        "A": _ticker("A", 100_000_000),
        "B": _ticker("B", 100_000_000),
    }
    opps = score_opportunities(funding, tickers, excluded=["A"])
    assert {o.symbol for o in opps} == {"B"}


def test_stability_factor_penalises_flippy_history() -> None:
    funding = [_funding("STABLE", 0.0003), _funding("FLIPPY", 0.0003)]
    tickers = {
        "STABLE": _ticker("STABLE", 100_000_000),
        "FLIPPY": _ticker("FLIPPY", 100_000_000),
    }
    history = {
        "STABLE": [_funding("STABLE", 0.0003) for _ in range(10)],
        "FLIPPY": [
            _funding("FLIPPY", 0.0003 if i % 2 == 0 else -0.0003) for i in range(10)
        ],
    }
    opps = score_opportunities(funding, tickers, history=history)
    by_symbol = {o.symbol: o for o in opps}
    assert by_symbol["STABLE"].score > by_symbol["FLIPPY"].score
    assert by_symbol["STABLE"].stability == 1.0
    assert by_symbol["FLIPPY"].stability < 1.0
