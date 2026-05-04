"""Portfolio: tracks open delta-neutral positions and reports metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Position:
    """An open delta-neutral position (spot long + perp short)."""

    symbol: str
    notional_per_leg: float
    spot_capital: float
    short_margin: float
    entry_funding_rate: float
    entry_apy: float
    entry_price: float
    opened_at: datetime
    funding_collected_usd: float = 0.0
    last_funding_apy: float = 0.0

    @property
    def capital_used(self) -> float:
        return self.spot_capital + self.short_margin

    def collect_funding(self, *, funding_rate: float, mark_price: float) -> float:
        """Apply a funding event. Returns the USD collected (can be negative)."""
        amount = self.notional_per_leg * funding_rate
        self.funding_collected_usd += amount
        self.last_funding_apy = funding_rate * 3 * 365 * 100
        return amount


@dataclass
class Portfolio:
    """In-memory portfolio of open delta-neutral positions."""

    capital_total: float
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0

    @property
    def n_open(self) -> int:
        return len(self.positions)

    @property
    def capital_used(self) -> float:
        return sum(p.capital_used for p in self.positions.values())

    @property
    def capital_available(self) -> float:
        return self.capital_total - self.capital_used + self.realized_pnl

    @property
    def total_funding_collected(self) -> float:
        return sum(p.funding_collected_usd for p in self.positions.values())

    @property
    def equity(self) -> float:
        return self.capital_total + self.realized_pnl + self.total_funding_collected

    def open(self, position: Position) -> None:
        if position.symbol in self.positions:
            raise ValueError(f"Position already exists for {position.symbol}")
        if position.capital_used > self.capital_available + 1e-6:
            raise ValueError(
                f"Insufficient capital: need {position.capital_used:.2f}, "
                f"have {self.capital_available:.2f}"
            )
        self.positions[position.symbol] = position

    def close(self, symbol: str, *, exit_price: float | None = None) -> Position:
        """Close a position; the accumulated funding becomes realized PnL."""
        if symbol not in self.positions:
            raise KeyError(symbol)
        pos = self.positions.pop(symbol)
        self.realized_pnl += pos.funding_collected_usd
        # Net of the now-realised funding so equity stays consistent.
        pos.funding_collected_usd = 0.0
        return pos

    def get(self, symbol: str) -> Position | None:
        return self.positions.get(symbol)

    def worst_apy(self) -> tuple[str, float] | None:
        """Symbol and last-known APY of the worst-performing open position."""
        if not self.positions:
            return None
        worst = min(self.positions.values(), key=lambda p: p.last_funding_apy or p.entry_apy)
        return (worst.symbol, worst.last_funding_apy or worst.entry_apy)


def make_position(
    *,
    symbol: str,
    notional_per_leg: float,
    spot_capital: float,
    short_margin: float,
    entry_funding_rate: float,
    entry_price: float,
    now: datetime | None = None,
) -> Position:
    return Position(
        symbol=symbol,
        notional_per_leg=notional_per_leg,
        spot_capital=spot_capital,
        short_margin=short_margin,
        entry_funding_rate=entry_funding_rate,
        entry_apy=entry_funding_rate * 3 * 365 * 100,
        entry_price=entry_price,
        opened_at=now or datetime.now(tz=timezone.utc),
        last_funding_apy=entry_funding_rate * 3 * 365 * 100,
    )
