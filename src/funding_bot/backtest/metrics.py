"""Performance metrics derived from a backtest equity curve."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import sqrt


@dataclass(frozen=True)
class BacktestMetrics:
    starting_equity: float
    ending_equity: float
    total_return_pct: float
    annualised_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    n_ticks: int
    n_opens: int
    n_closes: int
    funding_collected: float
    fees_paid: float
    duration_days: float
    win_rate_pct: float

    def render(self) -> str:
        return (
            f"Period:               {self.duration_days:.1f} days\n"
            f"Starting equity:      ${self.starting_equity:,.2f}\n"
            f"Ending equity:        ${self.ending_equity:,.2f}\n"
            f"Total return:         {self.total_return_pct:+.2f}%\n"
            f"Annualised return:    {self.annualised_return_pct:+.2f}% APY\n"
            f"Max drawdown:         {self.max_drawdown_pct:.2f}%\n"
            f"Sharpe ratio:         {self.sharpe_ratio:.2f}\n"
            f"Funding collected:    ${self.funding_collected:+,.2f}\n"
            f"Fees paid:            ${self.fees_paid:,.2f}\n"
            f"Opens / closes:       {self.n_opens} / {self.n_closes}\n"
            f"Profitable ticks:     {self.win_rate_pct:.1f}%\n"
            f"Ticks executed:       {self.n_ticks}"
        )


def compute_metrics(
    *,
    equity_curve: list[tuple[datetime, float]],
    starting_equity: float,
    n_opens: int,
    n_closes: int,
    funding_collected: float,
    fees_paid: float,
) -> BacktestMetrics:
    if not equity_curve:
        return BacktestMetrics(
            starting_equity=starting_equity,
            ending_equity=starting_equity,
            total_return_pct=0.0,
            annualised_return_pct=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            n_ticks=0,
            n_opens=n_opens,
            n_closes=n_closes,
            funding_collected=funding_collected,
            fees_paid=fees_paid,
            duration_days=0.0,
            win_rate_pct=0.0,
        )

    ending_equity = equity_curve[-1][1]
    duration = equity_curve[-1][0] - equity_curve[0][0]
    duration_days = max(duration / timedelta(days=1), 1e-9)
    total_return = (ending_equity / starting_equity) - 1
    total_return_pct = total_return * 100

    annualised = ((1 + total_return) ** (365 / duration_days) - 1) * 100 if duration_days > 0 else 0.0

    # Drawdown: worst drop from any prior peak.
    peak = -float("inf")
    max_dd = 0.0
    for _, value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)
    max_dd_pct = max_dd * 100

    # Sharpe ratio: per-tick return distribution vs zero risk-free.
    returns: list[float] = []
    for prev, curr in zip(equity_curve, equity_curve[1:]):
        if prev[1] > 0:
            returns.append(curr[1] / prev[1] - 1)
    win_rate = (
        100 * sum(1 for r in returns if r > 0) / len(returns) if returns else 0.0
    )
    if len(returns) > 1:
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std = sqrt(var)
        sharpe = mean / std * sqrt(len(returns) / max(duration_days, 1) * 365) if std > 0 else 0.0
    else:
        sharpe = 0.0

    return BacktestMetrics(
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        total_return_pct=total_return_pct,
        annualised_return_pct=annualised,
        max_drawdown_pct=max_dd_pct,
        sharpe_ratio=sharpe,
        n_ticks=len(equity_curve),
        n_opens=n_opens,
        n_closes=n_closes,
        funding_collected=funding_collected,
        fees_paid=fees_paid,
        duration_days=duration_days,
        win_rate_pct=win_rate,
    )
