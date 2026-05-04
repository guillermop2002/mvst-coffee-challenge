"""Paper executor: apply Decisions to a Portfolio with simulated fills.

Models fees and slippage so paper PnL is comparable to what a live bot
would realise. Defaults reflect Binance taker rates as of 2026-Q1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from funding_bot.strategy.decisions import (
    ClosePosition,
    Decision,
    HoldPosition,
    OpenPosition,
)
from funding_bot.strategy.portfolio import Portfolio, make_position


@dataclass(frozen=True)
class FeeModel:
    """Round-trip fee + slippage assumption for one delta-neutral position."""

    spot_taker_bps: float = 10.0       # 0.10%
    futures_taker_bps: float = 4.0     # 0.04%
    slippage_bps: float = 2.0          # 0.02% per side

    def open_cost(self, notional: float) -> float:
        """Cost to open one delta-neutral pair at the given notional."""
        bps = self.spot_taker_bps + self.futures_taker_bps + 2 * self.slippage_bps
        return notional * bps / 10_000

    def close_cost(self, notional: float) -> float:
        """Symmetric to open_cost."""
        return self.open_cost(notional)


@dataclass
class ExecutionEvent:
    timestamp: datetime
    action: str
    symbol: str
    detail: str
    pnl_delta: float = 0.0


@dataclass
class ExecutionResult:
    events: list[ExecutionEvent] = field(default_factory=list)
    fees_paid: float = 0.0
    n_opens: int = 0
    n_closes: int = 0


class PaperExecutor:
    def __init__(self, fee_model: FeeModel | None = None) -> None:
        self.fees = fee_model or FeeModel()

    def apply(
        self,
        *,
        portfolio: Portfolio,
        decisions: Sequence[Decision],
        prices: dict[str, float],
        now: datetime | None = None,
    ) -> ExecutionResult:
        now = now or datetime.now(tz=timezone.utc)
        result = ExecutionResult()

        # Apply CLOSEs first to free capital before any rotations open.
        for decision in decisions:
            if isinstance(decision, ClosePosition):
                self._close(decision, portfolio, prices, now, result)
            elif isinstance(decision, HoldPosition):
                continue

        for decision in decisions:
            if isinstance(decision, OpenPosition):
                self._open(decision, portfolio, prices, now, result)

        return result

    def _close(
        self,
        decision: ClosePosition,
        portfolio: Portfolio,
        prices: dict[str, float],
        now: datetime,
        result: ExecutionResult,
    ) -> None:
        position = portfolio.get(decision.symbol)
        if position is None:
            result.events.append(
                ExecutionEvent(
                    timestamp=now,
                    action="CLOSE_SKIPPED",
                    symbol=decision.symbol,
                    detail="no open position",
                )
            )
            return

        fee = self.fees.close_cost(position.notional_per_leg)
        # Charge the close fee against realised PnL.
        portfolio.realized_pnl -= fee
        portfolio.close(decision.symbol, exit_price=prices.get(decision.symbol))
        result.fees_paid += fee
        result.n_closes += 1
        result.events.append(
            ExecutionEvent(
                timestamp=now,
                action="CLOSE",
                symbol=decision.symbol,
                detail=decision.reason,
                pnl_delta=-fee,
            )
        )

    def _open(
        self,
        decision: OpenPosition,
        portfolio: Portfolio,
        prices: dict[str, float],
        now: datetime,
        result: ExecutionResult,
    ) -> None:
        sizing = decision.sizing
        if sizing.notional_per_leg <= 0:
            return

        if sizing.capital_used > portfolio.capital_available + 1e-6:
            result.events.append(
                ExecutionEvent(
                    timestamp=now,
                    action="OPEN_SKIPPED",
                    symbol=decision.symbol,
                    detail=f"insufficient capital ({sizing.capital_used:.2f} > "
                    f"{portfolio.capital_available:.2f})",
                )
            )
            return

        opp = decision.opportunity
        position = make_position(
            symbol=decision.symbol,
            notional_per_leg=sizing.notional_per_leg,
            spot_capital=sizing.spot_capital,
            short_margin=sizing.short_margin,
            entry_funding_rate=opp.funding.funding_rate,
            entry_price=opp.funding.mark_price,
            now=now,
        )
        portfolio.open(position)
        fee = self.fees.open_cost(sizing.notional_per_leg)
        portfolio.realized_pnl -= fee
        result.fees_paid += fee
        result.n_opens += 1
        result.events.append(
            ExecutionEvent(
                timestamp=now,
                action="OPEN",
                symbol=decision.symbol,
                detail=decision.reason,
                pnl_delta=-fee,
            )
        )

    def settle_funding(
        self,
        *,
        portfolio: Portfolio,
        funding_by_symbol: dict[str, tuple[float, float]],
        now: datetime | None = None,
    ) -> ExecutionResult:
        """Apply a round of funding payments. Each value is (rate, mark_price)."""
        now = now or datetime.now(tz=timezone.utc)
        result = ExecutionResult()
        for symbol, position in portfolio.positions.items():
            if symbol not in funding_by_symbol:
                continue
            rate, mark = funding_by_symbol[symbol]
            amount = position.collect_funding(funding_rate=rate, mark_price=mark)
            result.events.append(
                ExecutionEvent(
                    timestamp=now,
                    action="FUNDING",
                    symbol=symbol,
                    detail=f"rate={rate * 100:+.4f}% mark=${mark:,.2f}",
                    pnl_delta=amount,
                )
            )
        return result
