"""Legal hero candidate actions and practical sizing generation."""

from poker_trainer.models.action_aware import HeroActionKind, HeroCandidateAction
from poker_trainer.models.game_state import GameState
from poker_trainer.utils.exceptions import InvalidGameStateError

_BET_FRACTIONS = (0.25, 0.33, 0.50, 0.67, 0.75, 1.00)


def generate_candidate_actions(game_state: GameState) -> tuple[HeroCandidateAction, ...]:
    """Return de-duplicated currently legal actions and common sizes."""
    table = game_state.table_state
    if table is None:
        raise InvalidGameStateError("Action-aware analysis requires table state.")
    hero = table.hero
    stack = hero.stack if hero.stack > 0 else game_state.hero_stack
    if game_state.amount_to_call <= 0:
        candidates = [
            HeroCandidateAction(
                key="check",
                label="Check",
                kind=HeroActionKind.CHECK,
                additional_investment=0.0,
                target_round_contribution=hero.round_contribution,
            )
        ]
        for fraction in _BET_FRACTIONS:
            amount = min(stack, max(game_state.big_blind, game_state.pot_size * fraction))
            if amount > 0:
                candidates.append(
                    HeroCandidateAction(
                        key=f"bet_{int(fraction * 100)}",
                        label=f"Bet {int(fraction * 100)}% pot",
                        kind=HeroActionKind.BET,
                        additional_investment=amount,
                        target_round_contribution=hero.round_contribution + amount,
                    )
                )
        if stack > 0:
            candidates.append(
                HeroCandidateAction(
                    key="all_in",
                    label="All-in",
                    kind=HeroActionKind.ALL_IN,
                    additional_investment=stack,
                    target_round_contribution=hero.round_contribution + stack,
                )
            )
        return _deduplicate(candidates)

    candidates = [
        HeroCandidateAction(
            key="fold",
            label="Fold",
            kind=HeroActionKind.FOLD,
            additional_investment=0.0,
            target_round_contribution=hero.round_contribution,
        )
    ]
    call_amount = min(stack, game_state.amount_to_call)
    if call_amount >= stack:
        candidates.append(
            HeroCandidateAction(
                key="all_in_call",
                label="All-in call",
                kind=HeroActionKind.ALL_IN,
                additional_investment=stack,
                target_round_contribution=hero.round_contribution + stack,
            )
        )
        return tuple(candidates)
    candidates.append(
        HeroCandidateAction(
            key="call",
            label="Call",
            kind=HeroActionKind.CALL,
            additional_investment=call_amount,
            target_round_contribution=hero.round_contribution + call_amount,
        )
    )
    highest = max(player.round_contribution for player in table.players)
    if highest <= hero.round_contribution:
        highest = hero.round_contribution + game_state.amount_to_call
    minimum_increment = max(game_state.big_blind, highest - hero.round_contribution)
    targets = (
        ("min_raise", "Minimum raise", highest + minimum_increment),
        ("raise_2_5x", "Raise to 2.5x", highest * 2.5),
        ("raise_3x", "Raise to 3x", highest * 3.0),
        (
            "pot_raise",
            "Pot-sized raise",
            highest + game_state.pot_size + game_state.amount_to_call,
        ),
    )
    maximum_target = hero.round_contribution + stack
    for key, label, target in targets:
        capped_target = min(maximum_target, max(target, highest + minimum_increment))
        investment = capped_target - hero.round_contribution
        if investment < stack:
            candidates.append(
                HeroCandidateAction(
                    key=key,
                    label=label,
                    kind=HeroActionKind.RAISE,
                    additional_investment=investment,
                    target_round_contribution=capped_target,
                )
            )
    candidates.append(
        HeroCandidateAction(
            key="all_in",
            label="All-in",
            kind=HeroActionKind.ALL_IN,
            additional_investment=stack,
            target_round_contribution=maximum_target,
        )
    )
    return _deduplicate(candidates)


def _deduplicate(candidates: list[HeroCandidateAction]) -> tuple[HeroCandidateAction, ...]:
    seen: set[tuple[HeroActionKind, int]] = set()
    result: list[HeroCandidateAction] = []
    for candidate in candidates:
        identity = (candidate.kind, round(candidate.additional_investment * 100))
        size_identity = round(candidate.additional_investment * 100)
        if identity in seen:
            continue
        if candidate.kind in {
            HeroActionKind.BET,
            HeroActionKind.RAISE,
            HeroActionKind.ALL_IN,
        } and any(
            round(existing.additional_investment * 100) == size_identity
            and existing.kind in {HeroActionKind.BET, HeroActionKind.RAISE, HeroActionKind.ALL_IN}
            for existing in result
        ):
            continue
        seen.add(identity)
        result.append(candidate)
    return tuple(result)
