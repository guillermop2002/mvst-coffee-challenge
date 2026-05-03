"""Binance USDT-margined perpetual futures client.

This wraps the ccxt library to provide a typed interface for the data
we care about: funding rates, tickers, and historical funding history.

Public endpoints (no API key required) are used in Fase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import ccxt
from loguru import logger


FUNDING_PERIODS_PER_DAY = 3  # Binance: funding every 8 hours
DAYS_PER_YEAR = 365


@dataclass(frozen=True)
class FundingSnapshot:
    """Current funding rate snapshot for a single perpetual contract."""

    symbol: str
    funding_rate: float
    next_funding_time: datetime | None
    mark_price: float
    timestamp: datetime

    @property
    def apy(self) -> float:
        """Annualized return assuming current funding rate persists."""
        return self.funding_rate * FUNDING_PERIODS_PER_DAY * DAYS_PER_YEAR * 100


@dataclass(frozen=True)
class TickerSnapshot:
    """24h ticker stats for a perpetual contract."""

    symbol: str
    last_price: float
    quote_volume_24h: float
    timestamp: datetime


class BinanceClient:
    """Thin wrapper around ccxt's Binance USD-M futures client."""

    def __init__(self, *, testnet: bool = False, rate_limit_ms: int = 200) -> None:
        self._exchange = ccxt.binance(
            {
                "options": {"defaultType": "future"},
                "enableRateLimit": True,
                "rateLimit": rate_limit_ms,
            }
        )
        if testnet:
            self._exchange.set_sandbox_mode(True)
        logger.debug(
            "Initialized Binance client (testnet={})",
            testnet,
        )

    def load_markets(self) -> dict:
        return self._exchange.load_markets()

    def fetch_funding_rates(self) -> list[FundingSnapshot]:
        """Fetch current funding rate for every USDT-margined perpetual."""
        raw = self._exchange.fetch_funding_rates()
        snapshots: list[FundingSnapshot] = []
        for symbol, info in raw.items():
            try:
                snap = self._parse_funding(symbol, info)
            except (KeyError, TypeError, ValueError) as exc:
                logger.debug("Skipping {}: {}", symbol, exc)
                continue
            snapshots.append(snap)
        logger.info("Fetched funding rates for {} symbols", len(snapshots))
        return snapshots

    def fetch_tickers(self) -> dict[str, TickerSnapshot]:
        """Fetch 24h ticker stats for all perpetuals."""
        raw = self._exchange.fetch_tickers()
        out: dict[str, TickerSnapshot] = {}
        for symbol, info in raw.items():
            try:
                last = float(info.get("last") or 0.0)
                quote_volume = float(info.get("quoteVolume") or 0.0)
            except (TypeError, ValueError):
                continue
            ts = info.get("timestamp")
            timestamp = (
                datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                if ts
                else datetime.now(tz=timezone.utc)
            )
            out[symbol] = TickerSnapshot(
                symbol=symbol,
                last_price=last,
                quote_volume_24h=quote_volume,
                timestamp=timestamp,
            )
        return out

    def fetch_funding_history(
        self,
        symbol: str,
        *,
        since_ms: int | None = None,
        limit: int = 1000,
    ) -> list[FundingSnapshot]:
        """Fetch historical funding rate prints for a single symbol."""
        raw = self._exchange.fetch_funding_rate_history(symbol, since=since_ms, limit=limit)
        out: list[FundingSnapshot] = []
        for entry in raw:
            ts = entry.get("timestamp")
            if ts is None:
                continue
            out.append(
                FundingSnapshot(
                    symbol=symbol,
                    funding_rate=float(entry.get("fundingRate") or 0.0),
                    next_funding_time=None,
                    mark_price=float(entry.get("markPrice") or 0.0),
                    timestamp=datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                )
            )
        return out

    @staticmethod
    def _parse_funding(symbol: str, info: dict) -> FundingSnapshot:
        funding_rate = info.get("fundingRate")
        if funding_rate is None:
            raise ValueError("missing fundingRate")
        ts = info.get("timestamp") or 0
        next_ts = info.get("fundingTimestamp")
        return FundingSnapshot(
            symbol=symbol,
            funding_rate=float(funding_rate),
            next_funding_time=(
                datetime.fromtimestamp(next_ts / 1000, tz=timezone.utc) if next_ts else None
            ),
            mark_price=float(info.get("markPrice") or 0.0),
            timestamp=(
                datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                if ts
                else datetime.now(tz=timezone.utc)
            ),
        )
