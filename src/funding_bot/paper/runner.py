"""Paper trading runner: orchestrates a single tick or a long-running loop."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger

from funding_bot.config import BotConfig
from funding_bot.exchanges.binance import BinanceClient
from funding_bot.paper.executor import ExecutionResult, FeeModel, PaperExecutor
from funding_bot.paper.persistence import PaperStore
from funding_bot.strategy import (
    Portfolio,
    StrategyEngine,
    score_opportunities,
)


@dataclass
class TickReport:
    timestamp: datetime
    n_decisions: int
    n_opens: int
    n_closes: int
    fees_paid: float
    funding_collected: float
    portfolio_equity: float
    portfolio_open_positions: int


class PaperRunner:
    def __init__(
        self,
        config: BotConfig,
        *,
        store: PaperStore | None = None,
        client: BinanceClient | None = None,
        fee_model: FeeModel | None = None,
    ) -> None:
        self.config = config
        self.client = client or BinanceClient(rate_limit_ms=config.exchange.rate_limit_ms)
        self.executor = PaperExecutor(fee_model=fee_model)
        self.engine = StrategyEngine(config.strategy)
        self.store = store or PaperStore(config.storage.database_path)
        self._last_funding_at: dict[str, datetime] = {}

    def run_tick(self) -> TickReport:
        """Run a single decision tick: fetch → analyze → execute → persist."""
        now = datetime.now(tz=timezone.utc)
        session_id = self.store.get_or_create_session(self.config.strategy.capital_usd)
        portfolio = (
            self.store.load_portfolio(session_id)
            or Portfolio(capital_total=self.config.strategy.capital_usd)
        )

        snapshots = self.client.fetch_funding_rates()
        tickers = self.client.fetch_tickers()

        opportunities = score_opportunities(
            snapshots,
            tickers,
            min_volume_usd=self.config.filters.min_24h_volume_usd,
            excluded=self.config.filters.exclude_symbols,
        )

        decisions = self.engine.decide(opportunities=opportunities, portfolio=portfolio)
        prices = {s.symbol: s.mark_price for s in snapshots}

        funding_result = self._maybe_settle_funding(portfolio, snapshots, now)
        exec_result = self.executor.apply(
            portfolio=portfolio, decisions=decisions, prices=prices, now=now
        )
        # Anchor funding-window tracking to the current next-funding time for
        # every position currently open (existing or just opened this tick).
        self._update_funding_tracking(portfolio, snapshots)

        # Persist combined event log + portfolio state.
        self.store.save_portfolio(session_id, portfolio)
        self.store.append_events(session_id, funding_result.events + exec_result.events)

        funding_collected = sum(e.pnl_delta for e in funding_result.events)
        report = TickReport(
            timestamp=now,
            n_decisions=len(decisions),
            n_opens=exec_result.n_opens,
            n_closes=exec_result.n_closes,
            fees_paid=exec_result.fees_paid,
            funding_collected=funding_collected,
            portfolio_equity=portfolio.equity,
            portfolio_open_positions=portfolio.n_open,
        )

        logger.info(
            "tick: opens={} closes={} fees=${:.2f} funding=${:.2f} equity=${:,.2f}",
            report.n_opens,
            report.n_closes,
            report.fees_paid,
            report.funding_collected,
            report.portfolio_equity,
        )
        return report

    def _maybe_settle_funding(
        self,
        portfolio: Portfolio,
        snapshots,
        now: datetime,
    ) -> ExecutionResult:
        """Trigger funding accrual when the on-chain window has advanced.

        For each open position whose `next_funding_time` is now strictly
        later than the value we recorded on the previous tick, we treat
        the previous window as paid out and book the funding.
        """
        funding_to_settle: dict[str, tuple[float, float]] = {}
        for snap in snapshots:
            if snap.symbol not in portfolio.positions:
                continue
            next_time = snap.next_funding_time
            if next_time is None:
                continue
            last_seen = self._last_funding_at.get(snap.symbol)
            if last_seen is None:
                continue
            if next_time > last_seen:
                funding_to_settle[snap.symbol] = (snap.funding_rate, snap.mark_price)

        if not funding_to_settle:
            return ExecutionResult()
        return self.executor.settle_funding(
            portfolio=portfolio, funding_by_symbol=funding_to_settle, now=now
        )

    def _update_funding_tracking(self, portfolio: Portfolio, snapshots) -> None:
        for snap in snapshots:
            if snap.symbol in portfolio.positions and snap.next_funding_time is not None:
                self._last_funding_at[snap.symbol] = snap.next_funding_time

    def run_loop(self, *, interval_seconds: int = 300, max_ticks: int | None = None) -> None:
        """Run continuously: one tick every `interval_seconds`."""
        n = 0
        while max_ticks is None or n < max_ticks:
            try:
                self.run_tick()
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("tick failed: {}", exc)
            n += 1
            if max_ticks is not None and n >= max_ticks:
                break
            time.sleep(interval_seconds)
