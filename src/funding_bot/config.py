"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExchangeConfig(BaseModel):
    name: str = "binance"
    market_type: str = "future"
    rate_limit_ms: int = 200


class StrategyConfig(BaseModel):
    capital_usd: float = 10_000.0
    max_concurrent_positions: int = 3
    max_leverage: float = 3.0
    min_apy_threshold: float = 12.0
    rotation_hysteresis: float = 0.30
    kelly_fraction: float = 0.20
    max_position_pct: float = 0.40


class FiltersConfig(BaseModel):
    min_24h_volume_usd: float = 10_000_000.0
    min_open_interest_usd: float = 5_000_000.0
    exclude_symbols: list[str] = Field(default_factory=list)


class RiskConfig(BaseModel):
    max_drawdown_pct: float = 10.0
    margin_safety_ratio: float = 0.50
    funding_flip_close_threshold: float = 0.0


class StorageConfig(BaseModel):
    database_path: str = "data/funding_bot.db"
    retention_days: int = 365


class BotConfig(BaseModel):
    """Top-level bot configuration loaded from YAML."""

    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> BotConfig:
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)


class Secrets(BaseSettings):
    """Secrets loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True
    bot_mode: str = "paper"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


def load_config(path: str | Path = "config/default.yaml") -> BotConfig:
    return BotConfig.from_yaml(path)


def load_secrets() -> Secrets:
    return Secrets()
