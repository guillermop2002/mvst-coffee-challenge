"""Tests for the PositionSizer."""

import pytest

from funding_bot.config import StrategyConfig
from funding_bot.strategy.sizing import PositionSizer


def _sizer(**overrides) -> PositionSizer:
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
    return PositionSizer(StrategyConfig(**base))


def test_capital_split_among_slots() -> None:
    sizer = _sizer()
    per_slot = sizer.size_for_slot(available_capital=9_000, n_slots=3)
    # 9000/3 = 3000 < cap of 10000*0.4 = 4000
    assert per_slot == pytest.approx(3000)


def test_capital_capped_by_max_position_pct() -> None:
    sizer = _sizer()
    per_slot = sizer.size_for_slot(available_capital=20_000, n_slots=1)
    # 20000/1 = 20000 but capped at 4000
    assert per_slot == pytest.approx(4000)


def test_zero_slots_returns_zero() -> None:
    sizer = _sizer()
    assert sizer.size_for_slot(available_capital=10_000, n_slots=0) == 0.0


def test_leverage_math() -> None:
    """For L=3 and $4000 capital, notional should be $3000 per leg."""
    sizer = _sizer()
    res = sizer.compute(capital_for_position=4_000)
    # N = C * L/(L+1) = 4000 * 3/4 = 3000
    assert res.notional_per_leg == pytest.approx(3000)
    assert res.spot_capital == pytest.approx(3000)
    # margin = N/L = 3000/3 = 1000
    assert res.short_margin == pytest.approx(1000)
    # capital used = 3000 + 1000 = 4000 (matches input)
    assert res.capital_used == pytest.approx(4000)
    assert res.leverage == 3.0


def test_total_exposure_is_double_notional() -> None:
    sizer = _sizer()
    res = sizer.compute(capital_for_position=4_000)
    assert res.total_exposure == pytest.approx(2 * res.notional_per_leg)


def test_leverage_one_is_no_leverage() -> None:
    sizer = _sizer(max_leverage=1.0)
    res = sizer.compute(capital_for_position=2_000)
    # N = 2000 * 1/2 = 1000; margin = 1000/1 = 1000
    assert res.notional_per_leg == pytest.approx(1000)
    assert res.short_margin == pytest.approx(1000)
    assert res.capital_used == pytest.approx(2000)


def test_leverage_zero_raises() -> None:
    sizer = _sizer(max_leverage=0)
    with pytest.raises(ValueError):
        sizer.compute(capital_for_position=1_000)
