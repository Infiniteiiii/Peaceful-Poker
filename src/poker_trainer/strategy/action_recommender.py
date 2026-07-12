"""Transparent educational recommendation rules."""

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from poker_trainer.engine.outs_calculator import OutsResult
from poker_trainer.models.equity import EquityResult
from poker_trainer.models.game_state import GameState
from poker_trainer.models.recommendation import ConfidenceLevel, Recommendation
from poker_trainer.resource_path import resource_path
from poker_trainer.strategy.legal_actions import PlayerAction, legal_actions
from poker_trainer.strategy.pot_odds import calculate_pot_odds


@dataclass(frozen=True, slots=True)
class RecommendationThresholds:
    """Adjustable recommendation threshold values."""

    clear_call_margin: float = 0.05
    thin_call_margin: float = 0.0
    value_bet_equity: float = 0.62
    strong_raise_equity: float = 0.72
    low_confidence_margin: float = 0.03
    medium_confidence_margin: float = 0.08
    small_bet_fraction: float = 0.33
    medium_bet_fraction: float = 0.60
    large_bet_fraction: float = 0.85


@lru_cache(maxsize=1)
def load_recommendation_thresholds() -> RecommendationThresholds:
    """Load packaged recommendation thresholds with safe built-in defaults."""
    try:
        payload: Any = json.loads(
            resource_path("recommendation_thresholds.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return RecommendationThresholds()
    if not isinstance(payload, dict):
        return RecommendationThresholds()
    names = set(RecommendationThresholds.__dataclass_fields__)
    values = {key: float(value) for key, value in payload.items() if key in names}
    return RecommendationThresholds(**values)


def recommend_action(
    game_state: GameState,
    equity_result: EquityResult | None,
    outs_result: OutsResult | None = None,
    thresholds: RecommendationThresholds | None = None,
) -> Recommendation:
    """Return a qualified rule-based recommendation using only legal actions."""
    values = thresholds or load_recommendation_thresholds()
    legal = legal_actions(game_state)
    legal_labels = tuple(action.display_name for action in legal)
    assumptions = ("This is an educational rule-based recommendation, not a GTO solution.",)
    risks = ("Opponent ranges, future betting, and exploitative adjustments are simplified.",)
    if equity_result is None:
        return Recommendation(
            primary_action=PlayerAction.CHECK.display_name
            if PlayerAction.CHECK in legal
            else PlayerAction.FOLD.display_name,
            confidence=ConfidenceLevel.LOW,
            suggested_size=None,
            legal_alternatives=legal_labels,
            reasons=("Equity is unavailable, so only legal passive guidance is possible.",),
            risks=risks,
            assumptions=assumptions,
            explanation="Reliable betting guidance requires an equity estimate.",
        )

    equity = equity_result.total_equity
    pot_odds = calculate_pot_odds(game_state.pot_size, game_state.amount_to_call, equity)
    reasons = [f"Estimated pot-share equity is {equity:.1%}."]
    if outs_result is not None and outs_result.unique_outs:
        reasons.append(f"There are {len(outs_result.unique_outs)} apparent unique outs.")

    if game_state.amount_to_call == 0:
        if equity >= values.strong_raise_equity and PlayerAction.BET in legal:
            action = PlayerAction.BET
            size = max(game_state.big_blind, game_state.pot_size * values.large_bet_fraction)
            reasons.append("Equity is high enough for a large value bet under the current rules.")
        elif equity >= values.value_bet_equity and PlayerAction.BET in legal:
            action = PlayerAction.BET
            size = max(game_state.big_blind, game_state.pot_size * values.medium_bet_fraction)
            reasons.append("Equity is ahead of the value-bet threshold.")
        else:
            action = PlayerAction.CHECK
            size = None
            reasons.append("No bet is faced and the hand is not clearly above the value threshold.")
    else:
        margin = equity - pot_odds.required_equity
        reasons.append(f"Required equity to call is {pot_odds.required_equity:.1%}.")
        if margin < values.thin_call_margin and PlayerAction.FOLD in legal:
            action = PlayerAction.FOLD
            size = None
            reasons.append("Estimated equity is below the break-even calling threshold.")
        elif (
            margin >= values.clear_call_margin
            and equity >= values.strong_raise_equity
            and PlayerAction.RAISE in legal
        ):
            action = PlayerAction.RAISE
            size = max(
                game_state.amount_to_call * 2, game_state.pot_size * values.medium_bet_fraction
            )
            reasons.append(
                "Equity is comfortably above the call threshold and strong enough to raise."
            )
        else:
            action = (
                PlayerAction.ALL_IN
                if game_state.hero_stack == game_state.amount_to_call
                else PlayerAction.CALL
            )
            size = (
                game_state.amount_to_call if action is PlayerAction.CALL else game_state.hero_stack
            )
            reasons.append("Calling appears preferable based on entered pot odds and equity.")
    confidence = _confidence(abs(equity - pot_odds.required_equity), values)
    return Recommendation(
        primary_action=action.display_name,
        confidence=confidence,
        suggested_size=size,
        legal_alternatives=legal_labels,
        reasons=tuple(reasons),
        risks=risks,
        assumptions=(*assumptions, *equity_result.assumptions),
        explanation=(
            f"Based on the entered information and current assumptions, "
            f"{action.display_name.lower()} appears preferable."
        ),
    )


def _confidence(margin: float, thresholds: RecommendationThresholds) -> ConfidenceLevel:
    if margin >= thresholds.medium_confidence_margin:
        return ConfidenceLevel.HIGH
    if margin >= thresholds.low_confidence_margin:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW
