"""Exact final-hand probability calculations for known Hold'em boards."""

from collections import Counter
from dataclasses import dataclass
from itertools import combinations

from poker_trainer.engine.hand_evaluator import evaluate_best_hand
from poker_trainer.models.card import Card
from poker_trainer.models.deck import Deck
from poker_trainer.models.game_state import GameState, Street
from poker_trainer.models.hand import HandCategory


@dataclass(frozen=True, slots=True)
class FinalHandProbabilityResult:
    """Exact final-category and improvement probabilities."""

    current_category: HandCategory | None
    exact_category_probabilities: dict[HandCategory, float]
    at_least_category_probabilities: dict[HandCategory, float]
    improvement_probability: float
    runouts_examined: int
    calculation_method: str
    warnings: tuple[str, ...] = ()


def calculate_final_hand_probabilities(game_state: GameState) -> FinalHandProbabilityResult:
    """Enumerate future board runouts and final hero hand categories exactly."""
    if game_state.street is Street.PREFLOP:
        return _preflop_deferred_result()

    current_category = evaluate_best_hand(game_state.known_cards).category
    if game_state.street is Street.RIVER:
        exact = _zero_probabilities()
        exact[current_category] = 1.0
        return FinalHandProbabilityResult(
            current_category=current_category,
            exact_category_probabilities=exact,
            at_least_category_probabilities=_at_least_probabilities(exact),
            improvement_probability=0.0,
            runouts_examined=1,
            calculation_method="already_complete",
        )

    runouts = _future_runouts(game_state)
    counts: Counter[HandCategory] = Counter()
    improvements = 0
    for runout in runouts:
        final_board = (*game_state.community_cards, *runout)
        final_hand = evaluate_best_hand((*game_state.hero_cards, *final_board))
        counts[final_hand.category] += 1
        if final_hand.category > current_category:
            improvements += 1

    total = sum(counts.values())
    exact = {category: counts[category] / total if total else 0.0 for category in HandCategory}
    return FinalHandProbabilityResult(
        current_category=current_category,
        exact_category_probabilities=exact,
        at_least_category_probabilities=_at_least_probabilities(exact),
        improvement_probability=improvements / total if total else 0.0,
        runouts_examined=total,
        calculation_method="exact_enumeration",
    )


def _future_runouts(game_state: GameState) -> tuple[tuple[Card, ...], ...]:
    deck = Deck.standard()
    deck.remove_many(game_state.known_cards)
    remaining = deck.remaining()
    cards_needed = 5 - len(game_state.community_cards)
    if cards_needed == 1:
        return tuple((card,) for card in remaining)
    if cards_needed == 2:
        return tuple(combinations(remaining, 2))
    return ()


def _preflop_deferred_result() -> FinalHandProbabilityResult:
    exact = _zero_probabilities()
    return FinalHandProbabilityResult(
        current_category=None,
        exact_category_probabilities=exact,
        at_least_category_probabilities=_at_least_probabilities(exact),
        improvement_probability=0.0,
        runouts_examined=0,
        calculation_method="preflop_exact_enumeration_deferred",
        warnings=(
            "Full preflop exact five-card board enumeration is intentionally deferred "
            "in this stage.",
        ),
    )


def _zero_probabilities() -> dict[HandCategory, float]:
    return {category: 0.0 for category in HandCategory}


def _at_least_probabilities(exact: dict[HandCategory, float]) -> dict[HandCategory, float]:
    return {
        category: sum(
            probability
            for final_category, probability in exact.items()
            if final_category >= category
        )
        for category in HandCategory
    }
