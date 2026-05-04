"""Strategy engine: turns market data + portfolio into decisions.

The engine is **pure**: same inputs produce same outputs. It never touches
the network, persistence, or wall-clock; that lives in the paper-trading
or live-execution layers built on top.
"""

from __future__ import annotations

from typing import Sequence

from funding_bot.config import StrategyConfig
from funding_bot.strategy.decisions import (
    ClosePosition,
    Decision,
    HoldPosition,
    OpenPosition,
)
from funding_bot.strategy.portfolio import Portfolio
from funding_bot.strategy.scoring import Opportunity
from funding_bot.strategy.sizing import PositionSizer


class StrategyEngine:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.sizer = PositionSizer(config)

    def decide(
        self,
        *,
        opportunities: Sequence[Opportunity],
        portfolio: Portfolio,
    ) -> list[Decision]:
        """Produce the list of decisions to apply this tick.

        Order of operations:
          1. CLOSE open positions whose live APY has fallen below the
             configured floor (or flipped negative).
          2. HOLD remaining positions that are still healthy.
          3. ROTATE: if a candidate opportunity beats the worst-held APY
             by more than `rotation_hysteresis`, close that holding to
             free a slot. This is encoded as ClosePosition + OpenPosition.
          4. OPEN new positions in any remaining slots, ranked by score.
        """
        decisions: list[Decision] = []
        opp_by_symbol = {o.symbol: o for o in opportunities}

        # --- Step 1+2: classify existing holdings ---
        symbols_to_close: list[str] = []
        for symbol, pos in list(portfolio.positions.items()):
            opp = opp_by_symbol.get(symbol)
            current_apy = opp.apy if opp else pos.last_funding_apy
            if current_apy < self.config.min_apy_threshold:
                decisions.append(
                    ClosePosition(
                        symbol=symbol,
                        reason=f"APY {current_apy:.2f}% < threshold {self.config.min_apy_threshold:.2f}%",
                        current_apy=current_apy,
                    )
                )
                symbols_to_close.append(symbol)
            else:
                decisions.append(HoldPosition(symbol=symbol, current_apy=current_apy))

        held_after_step1 = {
            s: p for s, p in portfolio.positions.items() if s not in symbols_to_close
        }

        # --- Step 3: rotation ---
        # Find the best opportunity not currently held.
        new_candidates = [o for o in opportunities if o.symbol not in portfolio.positions]
        rotated_out: set[str] = set()
        rotated_in: list[Opportunity] = []

        if held_after_step1 and new_candidates:
            for cand in new_candidates:
                # Exit early once the candidate score no longer justifies any rotation.
                worst_symbol, worst_apy = min(
                    held_after_step1.items(),
                    key=lambda kv: kv[1].last_funding_apy or kv[1].entry_apy,
                )[0], min(
                    (p.last_funding_apy or p.entry_apy)
                    for p in held_after_step1.values()
                )
                threshold = worst_apy * (1 + self.config.rotation_hysteresis)
                if cand.apy <= threshold:
                    break
                if worst_symbol in rotated_out:
                    continue
                decisions.append(
                    ClosePosition(
                        symbol=worst_symbol,
                        reason=(
                            f"Rotate out: {worst_apy:.2f}% APY beaten by "
                            f"{cand.symbol} at {cand.apy:.2f}% (>+{self.config.rotation_hysteresis * 100:.0f}%)"
                        ),
                        current_apy=worst_apy,
                    )
                )
                rotated_out.add(worst_symbol)
                rotated_in.append(cand)
                # Remove from held set so the next candidate compares against the
                # next-worst remaining holding.
                held_after_step1 = {
                    s: p for s, p in held_after_step1.items() if s != worst_symbol
                }
                if not held_after_step1:
                    break

        # --- Step 4: open new positions ---
        held_count = len(held_after_step1)
        already_planned = len(rotated_in)
        free_slots = (
            self.config.max_concurrent_positions - held_count - already_planned
        )

        # Total opens = rotations (forced) + free slots filled by best remaining.
        already_assigned = {o.symbol for o in rotated_in} | rotated_out
        remaining_candidates = [
            o for o in new_candidates if o.symbol not in already_assigned
        ]
        opens_to_plan = list(rotated_in) + remaining_candidates[: max(0, free_slots)]

        if opens_to_plan:
            n_opens = len(opens_to_plan)
            # The available capital includes capital that *will be* freed by closes.
            freed_capital = sum(
                portfolio.positions[s].capital_used
                for s in (symbols_to_close + list(rotated_out))
                if s in portfolio.positions
            )
            available = portfolio.capital_available + freed_capital
            per_position_capital = self.sizer.size_for_slot(
                available_capital=available, n_slots=n_opens
            )

            for opp in opens_to_plan:
                if opp.apy < self.config.min_apy_threshold:
                    continue
                sizing = self.sizer.kelly_adjusted(
                    capital_for_position=per_position_capital, opp=opp
                )
                if sizing.notional_per_leg <= 0:
                    continue
                decisions.append(
                    OpenPosition(
                        opportunity=opp,
                        sizing=sizing,
                        reason=f"score={opp.score:.2f} apy={opp.apy:.2f}%",
                    )
                )

        return decisions
