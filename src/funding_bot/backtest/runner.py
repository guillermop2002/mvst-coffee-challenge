"""Backtest runner: replays historical funding through the live strategy.

We reuse the StrategyEngine and PaperExecutor, swapping the live exchange
client for the historical replay iterator. This guarantees the backtest
result is what the same strategy would have produced on the same data
in paper or live mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterator

from loguru import logger

from funding_bot.backtest.data import HistoricalLoader, HistoricalSnapshot
from funding_bot.backtest.metrics import BacktestMetrics, compute_metrics
from funding_bot.config import BotConfig
from funding_bot.exchanges.binance import FundingSnapshot, TickerSnapshot
from funding_bot.paper.executor import FeeModel, PaperExecutor
from funding_bot.strategy import (
    Portfolio,
    StrategyEngine,
    score_opportunities,
)


@dataclass
class BacktestResult:
    metrics: BacktestMetrics
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)


class BacktestRunner:
    """Step the strategy through historical funding prints in 8h windows."""

    FUNDING_INTERVAL = timedelta(hours=8)

    def __init__(
        self,
        config: BotConfig,
        loader: HistoricalLoader,
        *,
        fee_model: FeeModel | None = None,
        assumed_volume_usd: float = 200_000_000,
    ) -> None:
        self.config = config
        self.loader = loader
        self.executor = PaperExecutor(fee_model=fee_model)
        self.engine = StrategyEngine(config.strategy)
        self.assumed_volume_usd = assumed_volume_usd

    def run(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        symbols: list[str] | None = None,
    ) -> BacktestResult:
        portfolio = Portfolio(capital_total=self.config.strategy.capital_usd)
        equity_curve: list[tuple[datetime, float]] = []
        n_opens = 0
        n_closes = 0
        fees_paid = 0.0
        funding_collected = 0.0

        for ts, snaps in self.loader.replay(start=start, end=end, symbols=symbols):
            funding_snaps = self._to_funding_snapshots(ts, snaps)
            tickers = self._synthetic_tickers(snaps, ts)

            # Settle funding for currently held positions FIRST. The print
            # at this timestamp is the funding that just paid out.
            funding_to_settle = {
                s.symbol: (s.funding_rate, s.mark_price)
                for s in funding_snaps
                if s.symbol in portfolio.positions
            }
            if funding_to_settle:
                fr = self.executor.settle_funding(
                    portfolio=portfolio,
                    funding_by_symbol=funding_to_settle,
                    now=ts,
                )
                for ev in fr.events:
                    funding_collected += ev.pnl_delta

            # Then re-evaluate the strategy and execute any decisions.
            opportunities = score_opportunities(
                funding_snaps,
                tickers,
                min_volume_usd=self.config.filters.min_24h_volume_usd,
                excluded=self.config.filters.exclude_symbols,
            )
            decisions = self.engine.decide(
                opportunities=opportunities, portfolio=portfolio
            )
            prices = {s.symbol: s.mark_price for s in funding_snaps}
            res = self.executor.apply(
                portfolio=portfolio, decisions=decisions, prices=prices, now=ts
            )
            n_opens += res.n_opens
            n_closes += res.n_closes
            fees_paid += res.fees_paid

            equity_curve.append((ts, portfolio.equity))

        metrics = compute_metrics(
            equity_curve=equity_curve,
            starting_equity=self.config.strategy.capital_usd,
            n_opens=n_opens,
            n_closes=n_closes,
            funding_collected=funding_collected,
            fees_paid=fees_paid,
        )
        logger.info(
            "Backtest done: {} ticks, {} opens, {} closes, equity=${:,.2f}",
            len(equity_curve),
            n_opens,
            n_closes,
            equity_curve[-1][1] if equity_curve else 0,
        )
        return BacktestResult(metrics=metrics, equity_curve=equity_curve)

    def _to_funding_snapshots(
        self,
        ts: datetime,
        snaps: list[HistoricalSnapshot],
    ) -> list[FundingSnapshot]:
        next_funding = ts + self.FUNDING_INTERVAL
        return [
            FundingSnapshot(
                symbol=s.symbol,
                funding_rate=s.funding_rate,
                next_funding_time=next_funding,
                mark_price=s.mark_price,
                timestamp=ts,
            )
            for s in snaps
        ]

    def _synthetic_tickers(
        self,
        snaps: list[HistoricalSnapshot],
        ts: datetime,
    ) -> dict[str, TickerSnapshot]:
        """Backtest doesn't carry historical 24h volume, so synthesize one.

        Symbols already in our historical DB satisfied the live volume
        filter at download time, so assuming a constant `assumed_volume_usd`
        is a reasonable simplification.
        """
        return {
            s.symbol: TickerSnapshot(
                symbol=s.symbol,
                last_price=s.mark_price,
                quote_volume_24h=self.assumed_volume_usd,
                timestamp=ts,
            )
            for s in snaps
        }
