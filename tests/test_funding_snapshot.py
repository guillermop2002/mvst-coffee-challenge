"""Tests for FundingSnapshot APY math."""

from datetime import datetime, timezone

from funding_bot.exchanges.binance import FundingSnapshot


def _snap(rate: float) -> FundingSnapshot:
    return FundingSnapshot(
        symbol="BTC/USDT:USDT",
        funding_rate=rate,
        next_funding_time=None,
        mark_price=50_000.0,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_apy_positive_funding() -> None:
    # 0.01% per 8h * 3 periods/day * 365 days = 10.95% APY
    snap = _snap(0.0001)
    assert abs(snap.apy - 10.95) < 0.01


def test_apy_zero_funding() -> None:
    assert _snap(0.0).apy == 0.0


def test_apy_negative_funding() -> None:
    # Negative funding means longs are paid; bot should avoid these.
    snap = _snap(-0.0002)
    assert snap.apy < 0
    assert abs(snap.apy + 21.9) < 0.01


def test_apy_high_funding_realistic() -> None:
    # A 0.05% / 8h funding rate (typical bull market) = 54.75% APY
    snap = _snap(0.0005)
    assert abs(snap.apy - 54.75) < 0.01
