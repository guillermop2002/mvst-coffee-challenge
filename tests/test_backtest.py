"""End-to-end backtest tests with synthetic deterministic data."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from funding_bot.backtest.data import HistoricalLoader, HistoricalSnapshot
from funding_bot.backtest.metrics import compute_metrics
from funding_bot.backtest.runner import BacktestRunner
from funding_bot.config import BotConfig, FiltersConfig, StrategyConfig
from funding_bot.paper.executor import FeeModel


@pytest.fixture
def loader(tmp_path: Path) -> HistoricalLoader:
    return HistoricalLoader(tmp_path / "hist.db")


def _seed_constant_funding(
    loader: HistoricalLoader,
    *,
    symbol: str,
    rate: float,
    n_periods: int,
    start: datetime,
    price: float = 100.0,
) -> None:
    snaps = [
        HistoricalSnapshot(
            symbol=symbol,
            timestamp=start + i * timedelta(hours=8),
            funding_rate=rate,
            mark_price=price,
        )
        for i in range(n_periods)
    ]
    loader.insert(snaps)


def _config() -> BotConfig:
    return BotConfig(
        strategy=StrategyConfig(
            capital_usd=10_000,
            max_concurrent_positions=1,
            max_leverage=3.0,
            min_apy_threshold=12.0,
            kelly_fraction=0.20,
            max_position_pct=0.40,
            rotation_hysteresis=0.30,
        ),
        filters=FiltersConfig(min_24h_volume_usd=10_000_000),
    )


def test_replay_yields_in_chronological_order(loader: HistoricalLoader) -> None:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    _seed_constant_funding(loader, symbol="A", rate=0.0001, n_periods=5, start=start)
    times = [ts for ts, _ in loader.replay()]
    assert times == sorted(times)
    assert len(times) == 5


def test_backtest_accumulates_funding_constant_rate(loader: HistoricalLoader) -> None:
    """With constant +0.05% funding for 30 days, equity should rise predictably."""
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    n_periods = 90  # 30 days of 8h windows
    _seed_constant_funding(
        loader,
        symbol="A/USDT:USDT",
        rate=0.0005,
        n_periods=n_periods,
        start=start,
        price=100.0,
    )

    cfg = _config()
    runner = BacktestRunner(
        cfg,
        loader,
        fee_model=FeeModel(spot_taker_bps=0, futures_taker_bps=0, slippage_bps=0),
    )
    result = runner.run()

    assert result.metrics.n_opens == 1
    assert result.metrics.ending_equity > result.metrics.starting_equity
    # Notional from sizer: capital_for_position is min($10000/1, $10000*0.4)=$4000.
    # After Kelly adjustment with stability=1.0, kelly_fraction=0.20, the
    # confidence multiplier is min(1, 0.20*5)=1.0, so full $4000 used.
    # Notional = 4000 * 3/4 = $3000. Funding per period = 3000 * 0.0005 = $1.50.
    # The very first window pays nothing (we open at that timestamp),
    # so 89 funding payments * $1.50 = $133.50.
    expected_funding = (n_periods - 1) * 3000 * 0.0005
    assert result.metrics.funding_collected == pytest.approx(expected_funding, rel=0.05)


def test_backtest_no_opens_when_below_threshold(loader: HistoricalLoader) -> None:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    # 0.00005 -> 5.475% APY < 12% threshold
    _seed_constant_funding(
        loader, symbol="A/USDT:USDT", rate=0.00005, n_periods=30, start=start
    )
    runner = BacktestRunner(_config(), loader, fee_model=FeeModel())
    result = runner.run()

    assert result.metrics.n_opens == 0
    assert result.metrics.ending_equity == result.metrics.starting_equity


def test_backtest_with_fees_reduces_pnl(loader: HistoricalLoader) -> None:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    _seed_constant_funding(
        loader, symbol="A/USDT:USDT", rate=0.0005, n_periods=90, start=start
    )

    runner_no_fee = BacktestRunner(
        _config(),
        loader,
        fee_model=FeeModel(spot_taker_bps=0, futures_taker_bps=0, slippage_bps=0),
    )
    runner_with_fee = BacktestRunner(_config(), loader, fee_model=FeeModel())

    no_fee = runner_no_fee.run().metrics.ending_equity
    with_fee = runner_with_fee.run().metrics.ending_equity
    assert with_fee < no_fee


def test_metrics_handles_empty_curve() -> None:
    metrics = compute_metrics(
        equity_curve=[],
        starting_equity=10_000,
        n_opens=0,
        n_closes=0,
        funding_collected=0,
        fees_paid=0,
    )
    assert metrics.n_ticks == 0
    assert metrics.total_return_pct == 0.0


def test_metrics_max_drawdown() -> None:
    pts = [
        (datetime(2025, 1, 1, tzinfo=timezone.utc), 10_000),
        (datetime(2025, 1, 2, tzinfo=timezone.utc), 11_000),
        (datetime(2025, 1, 3, tzinfo=timezone.utc), 9_000),  # 18.18% DD from peak
        (datetime(2025, 1, 4, tzinfo=timezone.utc), 12_000),
    ]
    metrics = compute_metrics(
        equity_curve=pts,
        starting_equity=10_000,
        n_opens=1,
        n_closes=0,
        funding_collected=0,
        fees_paid=0,
    )
    assert abs(metrics.max_drawdown_pct - 18.18) < 0.1
    assert metrics.total_return_pct == pytest.approx(20.0)
