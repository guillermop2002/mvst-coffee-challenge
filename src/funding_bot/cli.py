"""Command-line interface for the funding rate bot."""

from __future__ import annotations

from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from funding_bot.config import load_config
from funding_bot.exchanges import BinanceClient
from funding_bot.paper import PaperRunner, PaperStore
from funding_bot.storage import Database
from funding_bot.strategy import (
    ClosePosition,
    HoldPosition,
    OpenPosition,
    Portfolio,
    StrategyEngine,
    score_opportunities,
)


app = typer.Typer(
    add_completion=False,
    help="Delta-neutral funding rate arbitrage bot.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def rates(
    config_path: Path = typer.Option("config/default.yaml", "--config", "-c"),
    top: int = typer.Option(20, "--top", "-n", help="Show top N opportunities by APY."),
    min_volume: float = typer.Option(
        None,
        "--min-volume",
        help="Override min 24h volume filter (USD).",
    ),
) -> None:
    """List current funding-rate opportunities ranked by annualised APY."""
    cfg = load_config(config_path)
    min_vol = min_volume if min_volume is not None else cfg.filters.min_24h_volume_usd

    client = BinanceClient(rate_limit_ms=cfg.exchange.rate_limit_ms)
    snapshots = client.fetch_funding_rates()
    tickers = client.fetch_tickers()

    rows = []
    for snap in snapshots:
        ticker = tickers.get(snap.symbol)
        volume = ticker.quote_volume_24h if ticker else 0.0
        if volume < min_vol:
            continue
        rows.append((snap, volume))

    rows.sort(key=lambda r: r[0].apy, reverse=True)
    rows = rows[:top]

    table = Table(title=f"Top {len(rows)} funding opportunities (Binance USD-M)")
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Funding (8h)", justify="right")
    table.add_column("APY", justify="right", style="green")
    table.add_column("Mark price", justify="right")
    table.add_column("24h volume", justify="right")

    for snap, volume in rows:
        table.add_row(
            snap.symbol,
            f"{snap.funding_rate * 100:+.4f}%",
            f"{snap.apy:+.2f}%",
            f"${snap.mark_price:,.4f}",
            f"${volume / 1e6:,.1f}M",
        )

    console.print(table)


@app.command()
def fetch(
    config_path: Path = typer.Option("config/default.yaml", "--config", "-c"),
) -> None:
    """Fetch current funding rates and tickers, persist to local DB."""
    cfg = load_config(config_path)
    db = Database(cfg.storage.database_path)

    client = BinanceClient(rate_limit_ms=cfg.exchange.rate_limit_ms)
    snapshots = client.fetch_funding_rates()
    tickers = client.fetch_tickers()

    n_funding = db.insert_funding(snapshots)
    n_tickers = db.insert_tickers(tickers.values())

    logger.info(
        "Stored {} funding snapshots, {} ticker snapshots in {}",
        n_funding,
        n_tickers,
        cfg.storage.database_path,
    )
    console.print(
        f"[green]Stored[/green] {n_funding} funding rows, "
        f"{n_tickers} ticker rows -> {cfg.storage.database_path}"
    )


@app.command()
def history(
    symbol: str = typer.Argument(..., help="Symbol, e.g. BTC/USDT:USDT"),
    days: int = typer.Option(30, "--days", "-d"),
    config_path: Path = typer.Option("config/default.yaml", "--config", "-c"),
) -> None:
    """Fetch and store historical funding prints for a symbol."""
    cfg = load_config(config_path)
    db = Database(cfg.storage.database_path)
    client = BinanceClient(rate_limit_ms=cfg.exchange.rate_limit_ms)

    from datetime import datetime, timedelta, timezone

    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    since_ms = int(since.timestamp() * 1000)

    history = client.fetch_funding_history(symbol, since_ms=since_ms, limit=1000)
    n = db.insert_funding(history)
    console.print(
        f"[green]Stored[/green] {n} historical prints for {symbol} (last {days} days)"
    )


@app.command()
def info(
    config_path: Path = typer.Option("config/default.yaml", "--config", "-c"),
) -> None:
    """Show DB stats and config summary."""
    cfg = load_config(config_path)
    db = Database(cfg.storage.database_path)

    table = Table(title="Funding bot status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_row("Database", str(cfg.storage.database_path))
    table.add_row("Funding rows stored", f"{db.count_funding_rows():,}")
    table.add_row("Capital configured", f"${cfg.strategy.capital_usd:,.0f}")
    table.add_row("Min APY threshold", f"{cfg.strategy.min_apy_threshold:.1f}%")
    table.add_row("Max leverage", f"{cfg.strategy.max_leverage:.1f}x")
    console.print(table)


@app.command()
def analyze(
    config_path: Path = typer.Option("config/default.yaml", "--config", "-c"),
) -> None:
    """Show the decisions the bot would make right now (empty portfolio)."""
    cfg = load_config(config_path)
    client = BinanceClient(rate_limit_ms=cfg.exchange.rate_limit_ms)

    snapshots = client.fetch_funding_rates()
    tickers = client.fetch_tickers()

    opportunities = score_opportunities(
        snapshots,
        tickers,
        min_volume_usd=cfg.filters.min_24h_volume_usd,
        excluded=cfg.filters.exclude_symbols,
    )

    portfolio = Portfolio(capital_total=cfg.strategy.capital_usd)
    engine = StrategyEngine(cfg.strategy)
    decisions = engine.decide(opportunities=opportunities, portfolio=portfolio)

    table = Table(
        title=f"Bot decisions (capital ${cfg.strategy.capital_usd:,.0f}, "
        f"max {cfg.strategy.max_concurrent_positions} positions)"
    )
    table.add_column("Action", style="bold")
    table.add_column("Symbol")
    table.add_column("APY", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Notional/leg", justify="right")
    table.add_column("Capital used", justify="right")
    table.add_column("Reason")

    for d in decisions:
        if isinstance(d, OpenPosition):
            table.add_row(
                "[green]OPEN[/green]",
                d.symbol,
                f"{d.opportunity.apy:+.2f}%",
                f"{d.opportunity.score:.2f}",
                f"${d.sizing.notional_per_leg:,.0f}",
                f"${d.sizing.capital_used:,.0f}",
                d.reason,
            )
        elif isinstance(d, ClosePosition):
            table.add_row(
                "[red]CLOSE[/red]",
                d.symbol,
                f"{d.current_apy:+.2f}%",
                "-",
                "-",
                "-",
                d.reason,
            )
        elif isinstance(d, HoldPosition):
            table.add_row(
                "[yellow]HOLD[/yellow]",
                d.symbol,
                f"{d.current_apy:+.2f}%",
                "-",
                "-",
                "-",
                "-",
            )

    console.print(table)
    n_open = sum(1 for d in decisions if isinstance(d, OpenPosition))
    console.print(
        f"\n[bold]Summary:[/bold] {n_open} position(s) to open, "
        f"top opportunity: {opportunities[0].symbol if opportunities else 'none'}"
        + (f" @ {opportunities[0].apy:+.2f}% APY" if opportunities else "")
    )


@app.command()
def paper(
    config_path: Path = typer.Option("config/default.yaml", "--config", "-c"),
    interval: int = typer.Option(
        300, "--interval", "-i", help="Seconds between ticks in loop mode."
    ),
    once: bool = typer.Option(False, "--once", help="Run a single tick and exit."),
    reset: bool = typer.Option(False, "--reset", help="Reset paper session before run."),
) -> None:
    """Run the bot in paper-trading mode against live Binance market data."""
    cfg = load_config(config_path)
    if reset:
        PaperStore(cfg.storage.database_path).reset()
        console.print("[yellow]Paper session reset.[/yellow]")

    runner = PaperRunner(cfg)
    if once:
        report = runner.run_tick()
        console.print(
            f"[green]Tick done.[/green] equity=${report.portfolio_equity:,.2f} "
            f"opens={report.n_opens} closes={report.n_closes} "
            f"fees=${report.fees_paid:.2f} funding=${report.funding_collected:.2f}"
        )
        return

    console.print(
        f"[green]Starting paper loop.[/green] interval={interval}s, Ctrl+C to stop."
    )
    try:
        runner.run_loop(interval_seconds=interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user.[/yellow]")


@app.command(name="paper-status")
def paper_status(
    config_path: Path = typer.Option("config/default.yaml", "--config", "-c"),
    n_events: int = typer.Option(20, "--events", "-e"),
) -> None:
    """Show current paper portfolio + recent events."""
    cfg = load_config(config_path)
    store = PaperStore(cfg.storage.database_path)
    session_id = store.get_or_create_session(cfg.strategy.capital_usd)
    portfolio = store.load_portfolio(session_id)
    if portfolio is None:
        console.print("[yellow]No paper session yet. Run `funding-bot paper --once` first.[/yellow]")
        return

    pos_table = Table(title=f"Open positions ({portfolio.n_open})")
    pos_table.add_column("Symbol", style="cyan")
    pos_table.add_column("Notional", justify="right")
    pos_table.add_column("Entry APY", justify="right")
    pos_table.add_column("Last APY", justify="right")
    pos_table.add_column("Funding $", justify="right", style="green")
    for p in portfolio.positions.values():
        pos_table.add_row(
            p.symbol,
            f"${p.notional_per_leg:,.0f}",
            f"{p.entry_apy:+.2f}%",
            f"{p.last_funding_apy:+.2f}%",
            f"${p.funding_collected_usd:+.4f}",
        )
    console.print(pos_table)

    summary = Table(title="Portfolio summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", justify="right")
    summary.add_row("Capital total", f"${portfolio.capital_total:,.2f}")
    summary.add_row("Realized PnL", f"${portfolio.realized_pnl:+,.4f}")
    summary.add_row("Funding collected", f"${portfolio.total_funding_collected:+,.4f}")
    summary.add_row("Equity", f"${portfolio.equity:,.2f}")
    summary.add_row("Open positions", str(portfolio.n_open))
    console.print(summary)

    events = store.recent_events(session_id, limit=n_events)
    if events:
        ev_table = Table(title=f"Last {len(events)} events")
        ev_table.add_column("Time")
        ev_table.add_column("Action")
        ev_table.add_column("Symbol")
        ev_table.add_column("PnL Δ", justify="right")
        ev_table.add_column("Detail")
        for e in events:
            color = "green" if e.pnl_delta > 0 else ("red" if e.pnl_delta < 0 else "white")
            ev_table.add_row(
                e.timestamp.strftime("%Y-%m-%d %H:%M"),
                e.action,
                e.symbol,
                f"[{color}]${e.pnl_delta:+.4f}[/{color}]",
                e.detail,
            )
        console.print(ev_table)


if __name__ == "__main__":
    app()
