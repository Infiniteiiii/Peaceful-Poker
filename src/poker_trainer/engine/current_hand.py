"""Current hero-hand analysis for each Hold'em street."""

from dataclasses import dataclass

from poker_trainer.engine.hand_evaluator import evaluate_best_hand
from poker_trainer.models.card import Card
from poker_trainer.models.game_state import GameState, Street
from poker_trainer.models.hand import EvaluatedHand


@dataclass(frozen=True, slots=True)
class CurrentHandAnalysis:
    """Structured description of the hero's current made or preflop hand."""

    street: Street
    description: str
    is_preflop: bool
    evaluated_hand: EvaluatedHand | None
    best_five_cards: tuple[Card, ...]
    hero_cards_used: int


def analyze_current_hand(game_state: GameState) -> CurrentHandAnalysis:
    """Analyze the hero's current hand without inventing preflop made hands."""
    if game_state.street is Street.PREFLOP:
        return CurrentHandAnalysis(
            street=game_state.street,
            description=_describe_preflop(tuple(game_state.hero_cards)),
            is_preflop=True,
            evaluated_hand=None,
            best_five_cards=(),
            hero_cards_used=2,
        )

    evaluated = evaluate_best_hand(game_state.known_cards)
    hero_cards_used = sum(1 for card in game_state.hero_cards if card in evaluated.cards)
    return CurrentHandAnalysis(
        street=game_state.street,
        description=evaluated.description,
        is_preflop=False,
        evaluated_hand=evaluated,
        best_five_cards=evaluated.cards,
        hero_cards_used=hero_cards_used,
    )


def _describe_preflop(hero_cards: tuple[Card, ...]) -> str:
    first, second = sorted(hero_cards, key=lambda card: card.rank_value, reverse=True)
    if first.rank == second.rank:
        return f"Pair of {first.rank.plural_name}"
    suitedness = "suited" if first.suit is second.suit else "offsuit"
    return f"{first.rank.display_name}-{second.rank.display_name} {suitedness}"
