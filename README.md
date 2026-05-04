# Funding Rate Arbitrage Bot

Bot de arbitraje delta-neutral sobre el funding rate de futuros perpetuos.
La estrategia consiste en mantener spot largo + perpetuo corto del mismo
activo, eliminando la exposición direccional, y cobrar el funding rate cada
8 horas.

> **Estado:** Fase 4/7 — backtesting sobre datos históricos.

## Roadmap

| Fase | Descripción | Estado |
|------|-------------|--------|
| 0 | Setup del proyecto | ✅ |
| 1 | Capa de datos (funding rates en vivo + storage) | ✅ |
| 2 | Motor de estrategia (scoring, sizing, rotación) | ✅ |
| 3 | Paper trading | ✅ |
| 4 | Backtesting con histórico | ✅ |
| 5 | Setup de cuenta + API keys (acción del usuario) | ⏳ |
| 6 | Ejecución real (testnet → mainnet) | ⏳ |
| 7 | Deploy 24/7 | ⏳ |

## Requisitos

- Python 3.11+
- `pip` o `uv`

## Instalación

```bash
# Clona el repo y entra
git clone https://github.com/guillermop2002/mvst-coffee-challenge.git
cd mvst-coffee-challenge
git checkout claude/github-integration-setup-evNZs

# Instala dependencias
pip install -e .

# Copia el archivo de entorno
cp .env.example .env
```

En Fase 1 todavía no hace falta tocar `.env` ni tener cuenta en Binance.
Las llamadas son a endpoints públicos.

## Uso (Fase 1)

```bash
# Lista las top 20 oportunidades de funding ahora mismo
funding-bot rates --top 20

# Filtra por volumen mínimo (USD)
funding-bot rates --min-volume 50000000

# Descarga snapshot a la base de datos local
funding-bot fetch

# Descarga histórico de 30 días para un símbolo
funding-bot history "BTC/USDT:USDT" --days 30

# Ver estado de la base de datos
funding-bot info

# Mostrar las decisiones que tomaría el bot ahora mismo
# (con portfolio vacío + capital configurado)
funding-bot analyze

# Paper trading: una sola pasada (open/close/funding sobre datos reales,
# sin dinero real)
funding-bot paper --once

# Paper trading en bucle (cada 5 min). Ctrl+C para parar.
funding-bot paper --interval 300

# Reiniciar la sesión de paper trading desde cero
funding-bot paper --once --reset

# Ver estado actual del portfolio paper + últimos eventos
funding-bot paper-status

# Backtesting: descargar histórico de los últimos 90 días para top 20 pares
funding-bot backtest-download --days 90 --top-n 20

# Replay del histórico contra la estrategia
funding-bot backtest-run --start-days-ago 90 --curve
```

## Configuración

Toda la configuración vive en `config/default.yaml`. Los parámetros clave:

- `strategy.capital_usd` — capital total disponible.
- `strategy.min_apy_threshold` — APY mínima para abrir posición.
- `strategy.max_leverage` — apalancamiento máximo del short (default 3x).
- `strategy.kelly_fraction` — fracción de Kelly para sizing (default 0.20).
- `filters.min_24h_volume_usd` — volumen mínimo para considerar un par.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Arquitectura

```
src/funding_bot/
├── cli.py              # CLI con typer
├── config.py           # Pydantic config + secrets
├── exchanges/
│   └── binance.py      # ccxt wrapper, FundingSnapshot, TickerSnapshot
├── storage/
│   └── db.py           # SQLite persistencia
├── strategy/
│   ├── scoring.py      # Opportunity scoring (APY × stability × liquidity)
│   ├── sizing.py       # Position sizer (Kelly fractional + leverage)
│   ├── portfolio.py    # Portfolio + Position dataclasses
│   ├── decisions.py    # OpenPosition / ClosePosition / HoldPosition
│   └── engine.py       # StrategyEngine (close → rotate → open)
├── paper/
│   ├── executor.py     # PaperExecutor (simulated fills, fee model)
│   ├── persistence.py  # PaperStore (SQLite portfolio + event log)
│   └── runner.py       # PaperRunner (one tick or loop)
└── backtest/
    ├── data.py         # HistoricalLoader (download + chronological replay)
    ├── runner.py       # BacktestRunner (replay → engine → executor)
    └── metrics.py      # APY, max drawdown, Sharpe, win rate

config/default.yaml     # Parámetros del bot
tests/                  # pytest
```

## Seguridad

- Los `.env` están en `.gitignore`. Nunca subir API keys.
- Las API keys que se usen en Fase 6 deben tener permisos:
  - ✅ Read
  - ✅ Spot Trading
  - ✅ Futures Trading
  - ❌ Withdraw (NO habilitar)
- Whitelist de IP recomendada en Binance.
