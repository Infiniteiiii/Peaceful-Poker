"""Transparent hand-aware opponent action policy."""

import json
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from poker_trainer.engine.board_analyzer import BoardAnalysis, OverallTexture
from poker_trainer.engine.hand_evaluator import evaluate_hand_score
from poker_trainer.models.action_aware import (
    ActionDistribution,
    OpponentAction,
    OpponentProfile,
    PolicyProfile,
    RelativeHandStrength,
    TablePlayer,
)
from poker_trainer.models.card import Card
from poker_trainer.models.hand import HandCategory
from poker_trainer.resource_path import resource_path
from poker_trainer.utils.exceptions import InvalidGameStateError


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """Current information available to the bounded opponent policy."""

    pot_size: float
    amount_to_call: float
    minimum_raise: float
    board_analysis: BoardAnalysis
    opponents_remaining: int
    position_fraction: float
    prior_aggression: int
    raises_so_far: int
    maximum_raises: int

    def __post_init__(self) -> None:
        if min(self.pot_size, self.amount_to_call, self.minimum_raise) < 0:
            raise InvalidGameStateError("Policy betting inputs cannot be negative.")
        if not 0 <= self.position_fraction <= 1:
            raise InvalidGameStateError("Position fraction must be from zero to one.")


@lru_cache(maxsize=1)
def load_opponent_profiles() -> dict[OpponentProfile, PolicyProfile]:
    """Load all documented profile assumptions from packaged JSON."""
    try:
        payload: Any = json.loads(
            resource_path("opponent_profiles.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidGameStateError("Opponent profile configuration could not be loaded.") from exc
    if not isinstance(payload, dict):
        raise InvalidGameStateError("Opponent profile configuration must be an object.")
    profiles: dict[OpponentProfile, PolicyProfile] = {}
    for profile in OpponentProfile:
        values = payload.get(profile.value)
        if not isinstance(values, dict):
            raise InvalidGameStateError(f"Missing opponent profile: {profile.value}.")
        try:
            profiles[profile] = PolicyProfile(
                profile=profile,
                preflop_range=str(values["preflop_range"]),
                postflop_range=str(values["postflop_range"]),
                fold_bias=float(values["fold_bias"]),
                call_bias=float(values["call_bias"]),
                aggression=float(values["aggression"]),
                reraise_frequency=float(values["reraise_frequency"]),
                bluff_frequency=float(values["bluff_frequency"]),
                value_raise_threshold=float(values["value_raise_threshold"]),
                size_sensitivity=float(values["size_sensitivity"]),
                position_sensitivity=float(values["position_sensitivity"]),
                stack_sensitivity=float(values["stack_sensitivity"]),
                board_sensitivity=float(values["board_sensitivity"]),
                prior_aggression_sensitivity=float(values["prior_aggression_sensitivity"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidGameStateError(
                f"Opponent profile {profile.value} contains invalid values."
            ) from exc
    return profiles


def classify_opponent_hand(
    hole_cards: tuple[Card, Card], board: tuple[Card, ...]
) -> RelativeHandStrength:
    """Classify current made strength and meaningful draw potential."""
    if not board:
        high, low = sorted((card.rank_value for card in hole_cards), reverse=True)
        if high == low and high >= 11:
            return RelativeHandStrength.VERY_STRONG
        if high == low or (high >= 13 and low >= 10):
            return RelativeHandStrength.STRONG_MADE_HAND
        if high >= 11 and low >= 9:
            return RelativeHandStrength.MEDIUM_MADE_HAND
        return RelativeHandStrength.VERY_WEAK

    score = evaluate_hand_score((*hole_cards, *board))
    category = HandCategory(score[0])
    draw = _has_flush_draw((*hole_cards, *board)) or _has_straight_draw((*hole_cards, *board))
    if category >= HandCategory.FULL_HOUSE:
        return RelativeHandStrength.VERY_STRONG
    if category >= HandCategory.STRAIGHT:
        return RelativeHandStrength.STRONG_MADE_HAND
    if category in {HandCategory.THREE_OF_A_KIND, HandCategory.TWO_PAIR}:
        return RelativeHandStrength.STRONG_MADE_HAND
    if category is HandCategory.PAIR:
        paired_rank = score[1][0]
        board_high = max(card.rank_value for card in board)
        if paired_rank >= board_high:
            return RelativeHandStrength.MEDIUM_MADE_HAND
        return RelativeHandStrength.DRAW if draw else RelativeHandStrength.WEAK_SHOWDOWN_VALUE
    if draw:
        return RelativeHandStrength.DRAW
    if max(card.rank_value for card in hole_cards) > max(card.rank_value for card in board):
        return RelativeHandStrength.WEAK_SHOWDOWN_VALUE
    return RelativeHandStrength.VERY_WEAK


def opponent_action_distribution(
    player: TablePlayer,
    hole_cards: tuple[Card, Card],
    board: tuple[Card, ...],
    context: PolicyContext,
    profile_override: PolicyProfile | None = None,
) -> ActionDistribution:
    """Return a normalized distribution over legal hand-aware actions."""
    if not player.can_act:
        raise InvalidGameStateError("Folded, all-in, or ineligible players cannot act.")
    profile = profile_override or load_opponent_profiles()[player.profile]
    strength = classify_opponent_hand(hole_cards, board)
    strength_value = _strength_value(strength)
    legal = legal_opponent_actions(player, context)
    if context.amount_to_call > 0:
        weights = _facing_bet_weights(player, profile, strength_value, legal, context)
    else:
        weights = _checked_to_weights(player, profile, strength_value, legal, context)
    probabilities = _normalize(weights)
    return ActionDistribution(
        probabilities=probabilities,
        explanation=(
            f"Profile: {profile.profile.display_name}.",
            f"Sampled hand class: {strength.value.replace('_', ' ')}.",
            "Weights account for bet size, position, stack depth, board texture, and aggression.",
        ),
    )


def legal_opponent_actions(
    player: TablePlayer, context: PolicyContext
) -> tuple[OpponentAction, ...]:
    """Return only actions legal for this opponent and betting context."""
    if context.amount_to_call <= 0:
        actions = [OpponentAction.CHECK]
        if player.stack > 0:
            actions.extend(
                [
                    OpponentAction.BET_SMALL,
                    OpponentAction.BET_MEDIUM,
                    OpponentAction.BET_LARGE,
                    OpponentAction.ALL_IN,
                ]
            )
        return tuple(actions)
    actions = [OpponentAction.FOLD]
    if player.stack <= context.amount_to_call:
        actions.append(OpponentAction.ALL_IN)
        return tuple(actions)
    actions.append(OpponentAction.CALL)
    if (
        context.raises_so_far < context.maximum_raises
        and player.stack > context.amount_to_call + context.minimum_raise
    ):
        actions.append(OpponentAction.RAISE)
    actions.append(OpponentAction.ALL_IN)
    return tuple(actions)


def _facing_bet_weights(
    player: TablePlayer,
    profile: PolicyProfile,
    strength: float,
    legal: tuple[OpponentAction, ...],
    context: PolicyContext,
) -> dict[OpponentAction, float]:
    pot = max(context.pot_size, 1.0)
    bet_fraction = context.amount_to_call / pot
    spr = player.stack / pot
    position_bonus = (context.position_fraction - 0.5) * profile.position_sensitivity * 0.2
    range_bonus = _range_strength_adjustment(player.range_text)
    board_penalty = _board_danger(context.board_analysis) * profile.board_sensitivity * 0.10
    multiway_penalty = max(0, context.opponents_remaining - 1) * 0.025
    effective_strength = _clamp(
        strength + position_bonus + range_bonus - board_penalty - multiway_penalty
    )
    pressure = (
        bet_fraction * profile.size_sensitivity
        + context.prior_aggression * profile.prior_aggression_sensitivity * 0.10
    )
    weights: dict[OpponentAction, float] = {}
    if OpponentAction.FOLD in legal:
        weights[OpponentAction.FOLD] = max(
            0.001, (1.12 - effective_strength) * (0.35 + profile.fold_bias) * (1 + pressure)
        )
    if OpponentAction.CALL in legal:
        weights[OpponentAction.CALL] = max(
            0.001,
            (0.20 + effective_strength * 1.25)
            * profile.call_bias
            / (1 + bet_fraction * profile.size_sensitivity * 0.45),
        )
    if OpponentAction.RAISE in legal:
        value_component = max(0.0, effective_strength - profile.value_raise_threshold) * 5.0
        bluff_component = (1.0 - effective_strength) * profile.bluff_frequency * 0.55
        weights[OpponentAction.RAISE] = max(
            0.001,
            (value_component + bluff_component) * profile.aggression * profile.reraise_frequency,
        )
    if OpponentAction.ALL_IN in legal:
        forced_call = 1.5 if player.stack <= context.amount_to_call else 0.0
        stack_pressure = profile.stack_sensitivity / max(spr, 0.25)
        weights[OpponentAction.ALL_IN] = max(
            0.001,
            forced_call + effective_strength**3 * profile.aggression * stack_pressure * 0.35,
        )
    return weights


def _checked_to_weights(
    player: TablePlayer,
    profile: PolicyProfile,
    strength: float,
    legal: tuple[OpponentAction, ...],
    context: PolicyContext,
) -> dict[OpponentAction, float]:
    position_bonus = context.position_fraction * profile.position_sensitivity * 0.15
    board_factor = _board_danger(context.board_analysis) * profile.board_sensitivity
    initiative = _clamp(strength + position_bonus + profile.bluff_frequency * (1 - strength))
    aggression = profile.aggression * (0.75 + initiative)
    weights = {OpponentAction.CHECK: max(0.01, 1.25 - aggression - strength * 0.25)}
    if OpponentAction.BET_SMALL in legal:
        weights[OpponentAction.BET_SMALL] = max(
            0.001, aggression * (0.34 + profile.bluff_frequency + board_factor * 0.08)
        )
    if OpponentAction.BET_MEDIUM in legal:
        weights[OpponentAction.BET_MEDIUM] = max(0.001, aggression * initiative * 0.48)
    if OpponentAction.BET_LARGE in legal:
        weights[OpponentAction.BET_LARGE] = max(
            0.001, aggression * max(0.05, initiative - 0.42) * 0.42
        )
    if OpponentAction.ALL_IN in legal:
        spr = player.stack / max(context.pot_size, 1.0)
        weights[OpponentAction.ALL_IN] = max(
            0.001, aggression * strength**4 * profile.stack_sensitivity / max(spr, 0.3) * 0.10
        )
    return {action: weight for action, weight in weights.items() if action in legal}


def _normalize(weights: dict[OpponentAction, float]) -> dict[OpponentAction, float]:
    total = sum(max(0.0, weight) for weight in weights.values())
    if total <= 0:
        probability = 1.0 / len(weights)
        return {action: probability for action in weights}
    probabilities = {action: max(0.0, weight) / total for action, weight in weights.items()}
    correction = 1.0 - sum(probabilities.values())
    last = next(reversed(probabilities))
    probabilities[last] += correction
    return probabilities


def _strength_value(strength: RelativeHandStrength) -> float:
    return {
        RelativeHandStrength.VERY_WEAK: 0.07,
        RelativeHandStrength.WEAK_SHOWDOWN_VALUE: 0.25,
        RelativeHandStrength.DRAW: 0.48,
        RelativeHandStrength.MEDIUM_MADE_HAND: 0.62,
        RelativeHandStrength.STRONG_MADE_HAND: 0.82,
        RelativeHandStrength.VERY_STRONG: 0.97,
    }[strength]


def _range_strength_adjustment(range_text: str) -> float:
    normalized = range_text.strip().lower()
    if normalized in {"premium", "tight"}:
        return 0.06
    if normalized == "loose":
        return -0.03
    return 0.0


def _board_danger(board: BoardAnalysis) -> float:
    return {
        OverallTexture.NO_BOARD: 0.0,
        OverallTexture.DRY: 0.1,
        OverallTexture.MODERATELY_CONNECTED: 0.35,
        OverallTexture.WET: 0.65,
        OverallTexture.HIGHLY_COORDINATED: 0.9,
    }[board.overall_texture]


def _has_flush_draw(cards: tuple[Card, ...]) -> bool:
    return any(count == 4 for count in Counter(card.suit for card in cards).values())


def _has_straight_draw(cards: tuple[Card, ...]) -> bool:
    values = {card.rank_value for card in cards}
    if 14 in values:
        values.add(1)
    return any(len(values & set(range(start, start + 5))) == 4 for start in range(1, 11))


def _clamp(value: float) -> float:
    return max(0.01, min(0.99, value))
