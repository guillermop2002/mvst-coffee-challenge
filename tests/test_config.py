"""Tests for config loading."""

from pathlib import Path

from funding_bot.config import BotConfig, load_config


def test_load_default_config() -> None:
    cfg = load_config(Path("config/default.yaml"))
    assert cfg.exchange.name == "binance"
    assert cfg.strategy.capital_usd > 0
    assert cfg.strategy.min_apy_threshold > 0
    assert 0 < cfg.strategy.kelly_fraction <= 1


def test_config_defaults() -> None:
    cfg = BotConfig()
    assert cfg.strategy.max_leverage == 3.0
    assert cfg.risk.max_drawdown_pct == 10.0
