"""Opportunity scoring.

Combines current funding rate, 24h volume, and (when available) the
recent stability of the funding rate into a single comparable score.
The score is in APY units, penalised by lack of stability and rewarded
modestly for high liquidity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from funding_bot.exchanges.binance import FundingSnapshot, TickerSnapshot


@dataclass(frozen=True)
class Opportunity:
    """A scored funding-rate opportunity for a single perpetual."""

    funding: FundingSnapshot
    ticker: TickerSnapshot
    score: float
    stability: float = 1.0
    history: Sequence[FundingSnapshot] = field(default_factory=tuple)

    @property
    def symbol(self) -> str:
        return self.funding.symbol

    @property
    def apy(self) -> float:
        return self.funding.apy

    @property
    def volume_24h(self) -> float:
        return self.ticker.quote_volume_24h


def _stability_factor(history: Sequence[FundingSnapshot]) -> float:
    """Return a 0-1 multiplier penalising erratic funding rates.

    A funding rate that has been consistently positive over the lookback
    period is more reliable than one that flipped repeatedly. We compute
    the share of historical prints with the same sign as the most recent
    rate. With <3 data points we return 1.0 (no opinion).
    """
    if len(history) < 3:
        return 1.0
    last_sign = 1 if history[-1].funding_rate >= 0 else -1
    same_sign = sum(
        1 for h in history if (h.funding_rate >= 0) == (last_sign > 0)
    )
    return same_sign / len(history)


def _liquidity_factor(volume_usd: float) -> float:
    """Return a multiplier in [0.5, 1.2] based on 24h volume.

    Below $10M: 0.5 (illiquid, harder to enter/exit cleanly).
    Above $500M: 1.2 (institutional grade).
    Linear in between.
    """
    if volume_usd <= 10_000_000:
        return 0.5
    if volume_usd >= 500_000_000:
        return 1.2
    return 0.5 + 0.7 * (volume_usd - 10_000_000) / (500_000_000 - 10_000_000)


def score_opportunities(
    funding_snapshots: Sequence[FundingSnapshot],
    tickers: dict[str, TickerSnapshot],
    *,
    history: dict[str, Sequence[FundingSnapshot]] | None = None,
    min_volume_usd: float = 10_000_000,
    excluded: Sequence[str] = (),
) -> list[Opportunity]:
    """Score and rank funding-rate opportunities, highest score first."""
    excluded_set = set(excluded)
    history = history or {}
    out: list[Opportunity] = []
    for snap in funding_snapshots:
        if snap.symbol in excluded_set:
            continue
        ticker = tickers.get(snap.symbol)
        if ticker is None:
            continue
        if ticker.quote_volume_24h < min_volume_usd:
            continue
        if snap.funding_rate <= 0:
            # We only take the long-spot / short-perp side.
            continue

        symbol_history = history.get(snap.symbol, ())
        stability = _stability_factor(symbol_history)
        liquidity = _liquidity_factor(ticker.quote_volume_24h)
        score = snap.apy * stability * liquidity

        out.append(
            Opportunity(
                funding=snap,
                ticker=ticker,
                score=score,
                stability=stability,
                history=symbol_history,
            )
        )

    out.sort(key=lambda o: o.score, reverse=True)
    return out
