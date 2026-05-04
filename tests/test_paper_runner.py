"""Integration test: PaperRunner end-to-end with a stubbed exchange client."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from funding_bot.config import BotConfig, StorageConfig, StrategyConfig
from funding_bot.exchanges.binance import FundingSnapshot, TickerSnapshot
from funding_bot.paper.executor import FeeModel
from funding_bot.paper.persistence import PaperStore
from funding_bot.paper.runner import PaperRunner


TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


class StubClient:
    """Minimal stand-in for BinanceClient with controllable data."""

    def __init__(self) -> None:
        self.calls = 0
        self._next_funding = TS + timedelta(hours=8)

    def fetch_funding_rates(self) -> list[FundingSnapshot]:
        self.calls += 1
        # Two opportunities, one decent, one mediocre.
        return [
            FundingSnapshot(
                symbol="ETH/USDT:USDT",
                funding_rate=0.0005,
                next_funding_time=self._next_funding,
                mark_price=4_000.0,
                timestamp=TS,
            ),
            FundingSnapshot(
                symbol="SOL/USDT:USDT",
                funding_rate=0.00005,  # only 5.475% APY -> below threshold
                next_funding_time=self._next_funding,
                mark_price=200.0,
                timestamp=TS,
            ),
        ]

    def fetch_tickers(self) -> dict[str, TickerSnapshot]:
        return {
            "ETH/USDT:USDT": TickerSnapshot(
                symbol="ETH/USDT:USDT",
                last_price=4_000.0,
                quote_volume_24h=500_000_000,
                timestamp=TS,
            ),
            "SOL/USDT:USDT": TickerSnapshot(
                symbol="SOL/USDT:USDT",
                last_price=200.0,
                quote_volume_24h=300_000_000,
                timestamp=TS,
            ),
        }

    def advance_funding_window(self, hours: int = 8) -> None:
        self._next_funding += timedelta(hours=hours)


@pytest.fixture
def cfg(tmp_path: Path) -> BotConfig:
    return BotConfig(
        strategy=StrategyConfig(
            capital_usd=10_000,
            max_concurrent_positions=2,
            max_leverage=3.0,
            min_apy_threshold=12.0,
            kelly_fraction=0.20,
            max_position_pct=0.40,
        ),
        storage=StorageConfig(database_path=str(tmp_path / "paper.db")),
    )


def test_first_tick_opens_position(cfg: BotConfig) -> None:
    client = StubClient()
    runner = PaperRunner(
        cfg,
        store=PaperStore(cfg.storage.database_path),
        client=client,  # type: ignore[arg-type]
        fee_model=FeeModel(),
    )
    report = runner.run_tick()
    assert report.n_opens == 1
    assert report.n_closes == 0
    assert report.portfolio_open_positions == 1


def test_funding_settled_after_window_advance(cfg: BotConfig) -> None:
    client = StubClient()
    store = PaperStore(cfg.storage.database_path)
    runner = PaperRunner(
        cfg,
        store=store,
        client=client,  # type: ignore[arg-type]
        fee_model=FeeModel(spot_taker_bps=0, futures_taker_bps=0, slippage_bps=0),
    )
    runner.run_tick()  # opens ETH; primes _last_funding_at
    client.advance_funding_window(8)
    report = runner.run_tick()  # should settle funding now
    # 1500-ish notional * 0.0005 ~ $0.75
    assert report.funding_collected > 0
    portfolio = store.load_portfolio(store.get_or_create_session(cfg.strategy.capital_usd))
    assert portfolio is not None
    pos = portfolio.positions["ETH/USDT:USDT"]
    assert pos.funding_collected_usd > 0


def test_persistence_survives_runner_restart(cfg: BotConfig) -> None:
    client = StubClient()
    store = PaperStore(cfg.storage.database_path)
    runner = PaperRunner(
        cfg, store=store, client=client, fee_model=FeeModel()  # type: ignore[arg-type]
    )
    runner.run_tick()

    store2 = PaperStore(cfg.storage.database_path)
    session_id = store2.get_or_create_session(cfg.strategy.capital_usd)
    pf = store2.load_portfolio(session_id)
    assert pf is not None
    assert pf.n_open == 1
