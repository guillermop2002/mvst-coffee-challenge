"""Paper trading: simulated execution of strategy decisions."""

from funding_bot.paper.executor import FeeModel, PaperExecutor, ExecutionResult
from funding_bot.paper.persistence import PaperStore
from funding_bot.paper.runner import PaperRunner

__all__ = [
    "ExecutionResult",
    "FeeModel",
    "PaperExecutor",
    "PaperRunner",
    "PaperStore",
]
