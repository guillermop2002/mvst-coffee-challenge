"""Decision types emitted by the strategy engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from funding_bot.strategy.scoring import Opportunity
from funding_bot.strategy.sizing import SizingResult


@dataclass(frozen=True)
class OpenPosition:
    opportunity: Opportunity
    sizing: SizingResult
    reason: str

    @property
    def symbol(self) -> str:
        return self.opportunity.symbol


@dataclass(frozen=True)
class ClosePosition:
    symbol: str
    reason: str
    current_apy: float


@dataclass(frozen=True)
class HoldPosition:
    symbol: str
    current_apy: float


Decision = Union[OpenPosition, ClosePosition, HoldPosition]
