"""Position sizing for delta-neutral funding-rate trades.

A delta-neutral position holds (long spot N units) + (short perpetual N units).
Capital required for one position is therefore:
    spot_notional        = N      (paid in full, no leverage on spot)
    short_margin         = N / L   (margin posted for the short with leverage L)
    capital_used         = N + N/L = N * (L+1) / L

So given a capital budget C per position, the maximum equal notional is:
    N = C * L / (L + 1)
"""

from __future__ import annotations

from dataclasses import dataclass

from funding_bot.config import StrategyConfig
from funding_bot.strategy.scoring import Opportunity


@dataclass(frozen=True)
class SizingResult:
    """Output of the sizer for a single opportunity."""

    notional_per_leg: float
    spot_capital: float
    short_margin: float
    capital_used: float
    leverage: float

    @property
    def total_exposure(self) -> float:
        """Total notional summed across both legs (informational only)."""
        return self.notional_per_leg * 2


class PositionSizer:
    """Equal-weight sizer with leverage-aware capital allocation.

    For Fase 2 we keep things simple: distribute the available capital
    evenly across the chosen positions, capped by `max_position_pct`.
    Kelly-fraction tuning lives behind the same interface and can be
    layered in once we have empirical funding-rate variance.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self._config = config

    def size_for_slot(self, *, available_capital: float, n_slots: int) -> float:
        """Capital budget allocated to a single new position."""
        if n_slots <= 0:
            return 0.0
        per_slot = available_capital / n_slots
        cap = self._config.capital_usd * self._config.max_position_pct
        return min(per_slot, cap)

    def compute(self, *, capital_for_position: float) -> SizingResult:
        """Translate a per-position capital budget into leg notionals."""
        leverage = self._config.max_leverage
        if leverage <= 0:
            raise ValueError("max_leverage must be positive")

        notional = capital_for_position * leverage / (leverage + 1)
        spot_capital = notional
        short_margin = notional / leverage
        return SizingResult(
            notional_per_leg=notional,
            spot_capital=spot_capital,
            short_margin=short_margin,
            capital_used=spot_capital + short_margin,
            leverage=leverage,
        )

    def kelly_adjusted(
        self,
        *,
        capital_for_position: float,
        opp: Opportunity,
    ) -> SizingResult:
        """Kelly-fraction adjusted size.

        For delta-neutral funding-rate income the variance comes from
        the funding rate flipping or compressing. As a conservative proxy
        we treat the stability factor as a confidence multiplier, then
        apply the configured Kelly fraction.
        """
        confidence = opp.stability * self._config.kelly_fraction
        confidence = max(0.0, min(1.0, confidence * 5))
        adjusted_capital = capital_for_position * confidence
        return self.compute(capital_for_position=adjusted_capital)
