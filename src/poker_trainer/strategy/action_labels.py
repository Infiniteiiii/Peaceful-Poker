"""Canonical user-facing poker action terminology."""

from poker_trainer.models.action_aware import HeroActionKind
from poker_trainer.models.game_state import GameState
from poker_trainer.strategy.legal_actions import PlayerAction


def format_action(
    action: PlayerAction | HeroActionKind,
    game_state: GameState,
    *,
    additional_investment: float | None = None,
    target_round_contribution: float | None = None,
) -> str:
    """Describe an action using its betting context and exact chip convention."""
    kind = action.value
    if kind == "check":
        return "Check"
    if kind == "fold":
        return "Fold"
    if kind == "call":
        amount = (
            game_state.amount_to_call if additional_investment is None else additional_investment
        )
        if _uses_full_stack(game_state, amount):
            return f"Call all-in \u2014 {_chips(amount)}"
        return f"Call {_chips(amount)}" if amount > 0 else "Call"
    if kind == "bet":
        if additional_investment is not None and _uses_full_stack(
            game_state, additional_investment
        ):
            return f"Bet all-in \u2014 {_chips(additional_investment)}"
        return (
            f"Bet {_chips(additional_investment)}" if additional_investment is not None else "Bet"
        )
    if kind == "raise":
        if additional_investment is not None and _uses_full_stack(
            game_state, additional_investment
        ):
            target = (
                _current_contribution(game_state) + additional_investment
                if target_round_contribution is None
                else target_round_contribution
            )
            return f"Raise all-in to {_chips(target)}"
        return (
            f"Raise to {_chips(target_round_contribution)}"
            if target_round_contribution is not None
            else "Raise"
        )
    if kind != "all_in":
        raise ValueError(f"Unsupported action kind: {kind}")

    investment = _hero_stack(game_state) if additional_investment is None else additional_investment
    current_contribution = _current_contribution(game_state)
    target = (
        current_contribution + investment
        if target_round_contribution is None
        else target_round_contribution
    )
    if game_state.amount_to_call <= 0:
        return f"Bet all-in \u2014 {_chips(investment)}"
    if investment <= game_state.amount_to_call + 1e-9:
        return f"Call all-in \u2014 {_chips(investment)}"
    return f"Raise all-in to {_chips(target)}"


def format_legal_action(action: PlayerAction, game_state: GameState) -> str:
    """Format one legal action when no discretionary normal-action size is selected."""
    if action is PlayerAction.CALL:
        return format_action(
            action,
            game_state,
            additional_investment=min(_hero_stack(game_state), game_state.amount_to_call),
        )
    if action is PlayerAction.ALL_IN:
        stack = _hero_stack(game_state)
        current = (
            game_state.table_state.hero.round_contribution
            if game_state.table_state is not None
            else 0.0
        )
        return format_action(
            action,
            game_state,
            additional_investment=stack,
            target_round_contribution=current + stack,
        )
    return format_action(action, game_state)


def _hero_stack(game_state: GameState) -> float:
    hero_stack = (
        game_state.table_state.hero.stack
        if game_state.table_state is not None and game_state.table_state.hero.stack > 0
        else game_state.hero_stack
    )
    return min(hero_stack, game_state.effective_stack or hero_stack)


def _current_contribution(game_state: GameState) -> float:
    return (
        game_state.table_state.hero.round_contribution
        if game_state.table_state is not None
        else 0.0
    )


def _uses_full_stack(game_state: GameState, additional_investment: float) -> bool:
    stack = _hero_stack(game_state)
    return stack > 0 and additional_investment >= stack - 1e-9


def _chips(amount: float) -> str:
    rounded = round(amount, 2)
    if rounded.is_integer():
        return f"{int(rounded):,} chips"
    return f"{rounded:,.2f} chips"
