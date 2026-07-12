"""Draw detection for current Hold'em states."""

from collections import Counter
from dataclasses import dataclass
from enum import Enum

from poker_trainer.engine.hand_evaluator import evaluate_best_hand
from poker_trainer.models.card import Card, Rank, Suit
from poker_trainer.models.deck import Deck
from poker_trainer.models.game_state import GameState, Street
from poker_trainer.models.hand import HandCategory


class DrawType(Enum):
    """Supported educational draw labels."""

    FLUSH_DRAW = "flush_draw"
    BACKDOOR_FLUSH_DRAW = "backdoor_flush_draw"
    OPEN_ENDED_STRAIGHT_DRAW = "open_ended_straight_draw"
    GUTSHOT_STRAIGHT_DRAW = "gutshot_straight_draw"
    DOUBLE_GUTSHOT_STRAIGHT_DRAW = "double_gutshot_straight_draw"
    BACKDOOR_STRAIGHT_DRAW = "backdoor_straight_draw"
    TWO_OVERCARDS = "two_overcards"
    ONE_OVERCARD = "one_overcard"
    PAIR_IMPROVEMENT = "pair_improvement"
    TWO_PAIR_IMPROVEMENT = "two_pair_improvement"
    SET_IMPROVEMENT = "set_improvement"
    COMBINATION_DRAW = "combination_draw"


@dataclass(frozen=True, slots=True)
class Draw:
    """A structured draw with apparent outs and limitations."""

    draw_type: DrawType
    description: str
    outs: tuple[Card, ...]
    is_nut: bool | None = None
    uses_board_only: bool = False
    warnings: tuple[str, ...] = ()


_DIRTY_OUT_WARNING = (
    "Outs are apparent, not guaranteed clean, because opponent ranges are not modeled yet."
)


def detect_draws(game_state: GameState) -> tuple[Draw, ...]:
    """Return structured apparent draws for the hero's current state."""
    if game_state.street is Street.RIVER:
        return ()

    known = game_state.known_cards
    remaining = _remaining_cards(known)
    made_hand = _made_hand_or_none(game_state)
    draws: list[Draw] = []
    draws.extend(_flush_draws(game_state, remaining))
    draws.extend(_straight_draws(game_state, remaining, made_hand))
    draws.extend(_overcard_draws(game_state, remaining))
    draws.extend(_made_hand_improvement_draws(game_state, remaining, made_hand))

    primary_draw_count = sum(1 for draw in draws if draw.outs)
    if primary_draw_count >= 2:
        unique_outs = tuple(
            sorted({card for draw in draws for card in draw.outs}, key=lambda card: card.code)
        )
        draws.append(
            Draw(
                draw_type=DrawType.COMBINATION_DRAW,
                description="Multiple apparent draws are present.",
                outs=unique_outs,
                warnings=(_DIRTY_OUT_WARNING,),
            )
        )
    return tuple(draws)


def _remaining_cards(known_cards: tuple[Card, ...]) -> tuple[Card, ...]:
    deck = Deck.standard()
    deck.remove_many(known_cards)
    return deck.remaining()


def _made_hand_or_none(game_state: GameState) -> HandCategory | None:
    if game_state.street is Street.PREFLOP:
        return None
    return evaluate_best_hand(game_state.known_cards).category


def _flush_draws(game_state: GameState, remaining: tuple[Card, ...]) -> list[Draw]:
    if game_state.street is Street.PREFLOP:
        return []
    suit_counts = Counter(card.suit for card in game_state.known_cards)
    draws: list[Draw] = []
    for suit, count in suit_counts.items():
        hero_has_suit = any(card.suit is suit for card in game_state.hero_cards)
        suited_outs = tuple(card for card in remaining if card.suit is suit)
        if count == 4:
            draws.append(
                Draw(
                    draw_type=DrawType.FLUSH_DRAW,
                    description=f"{suit.display_name} flush draw.",
                    outs=suited_outs,
                    is_nut=_is_nut_flush_draw(tuple(game_state.hero_cards), suit),
                    uses_board_only=not hero_has_suit,
                    warnings=(_DIRTY_OUT_WARNING,),
                )
            )
        elif game_state.street is Street.FLOP and count == 3 and hero_has_suit:
            draws.append(
                Draw(
                    draw_type=DrawType.BACKDOOR_FLUSH_DRAW,
                    description=f"Backdoor {suit.display_name} flush possibility.",
                    outs=(),
                    is_nut=_is_nut_flush_draw(tuple(game_state.hero_cards), suit),
                    warnings=("Backdoor flushes require two future cards of the same suit.",),
                )
            )
    return draws


def _straight_draws(
    game_state: GameState,
    remaining: tuple[Card, ...],
    made_hand: HandCategory | None,
) -> list[Draw]:
    if game_state.street is Street.PREFLOP:
        return []
    if made_hand is not None and made_hand >= HandCategory.STRAIGHT:
        return []

    rank_values = {card.rank_value for card in game_state.known_cards}
    outs_by_rank = _straight_out_ranks(rank_values)
    if not outs_by_rank:
        if game_state.street is Street.FLOP and _has_backdoor_straight_shape(rank_values):
            return [
                Draw(
                    draw_type=DrawType.BACKDOOR_STRAIGHT_DRAW,
                    description="Backdoor straight possibility.",
                    outs=(),
                    warnings=("Backdoor straights require favorable turn and river cards.",),
                )
            ]
        return []

    out_cards = tuple(card for card in remaining if _rank_alias(card.rank_value) in outs_by_rank)
    if len(outs_by_rank) >= 2:
        draw_type = DrawType.OPEN_ENDED_STRAIGHT_DRAW
        description = "Open-ended straight draw."
        if not _has_open_ended_shape(rank_values, outs_by_rank):
            draw_type = DrawType.DOUBLE_GUTSHOT_STRAIGHT_DRAW
            description = "Double-gutshot straight draw."
    else:
        draw_type = DrawType.GUTSHOT_STRAIGHT_DRAW
        description = "Gutshot straight draw."
    return [
        Draw(
            draw_type=draw_type,
            description=description,
            outs=out_cards,
            warnings=(_DIRTY_OUT_WARNING,),
        )
    ]


def _overcard_draws(game_state: GameState, remaining: tuple[Card, ...]) -> list[Draw]:
    if game_state.street is Street.PREFLOP or not game_state.community_cards:
        return []
    board_high = max(card.rank_value for card in game_state.community_cards)
    overcard_ranks = tuple(
        sorted(
            {card.rank for card in game_state.hero_cards if card.rank_value > board_high},
            reverse=True,
        )
    )
    if not overcard_ranks:
        return []
    outs = tuple(card for card in remaining if card.rank in overcard_ranks)
    if len(overcard_ranks) == 2:
        return [
            Draw(
                draw_type=DrawType.TWO_OVERCARDS,
                description="Two overcards to the board.",
                outs=outs,
                warnings=(_DIRTY_OUT_WARNING,),
            )
        ]
    return [
        Draw(
            draw_type=DrawType.ONE_OVERCARD,
            description="One overcard to the board.",
            outs=outs,
            warnings=(_DIRTY_OUT_WARNING,),
        )
    ]


def _made_hand_improvement_draws(
    game_state: GameState,
    remaining: tuple[Card, ...],
    made_hand: HandCategory | None,
) -> list[Draw]:
    if made_hand is None:
        return []
    rank_counts = Counter(card.rank for card in game_state.known_cards)
    draws: list[Draw] = []
    if made_hand is HandCategory.PAIR:
        pair_rank = _ranks_with_count(rank_counts, 2)[0]
        out_ranks = {pair_rank, *[rank for rank, count in rank_counts.items() if count == 1]}
        draws.append(
            Draw(
                draw_type=DrawType.PAIR_IMPROVEMENT,
                description="One pair can improve to trips or two pair.",
                outs=tuple(card for card in remaining if card.rank in out_ranks),
                warnings=(_DIRTY_OUT_WARNING,),
            )
        )
    elif made_hand is HandCategory.TWO_PAIR:
        pair_ranks = set(_ranks_with_count(rank_counts, 2))
        draws.append(
            Draw(
                draw_type=DrawType.TWO_PAIR_IMPROVEMENT,
                description="Two pair can improve to a full house.",
                outs=tuple(card for card in remaining if card.rank in pair_ranks),
                warnings=(_DIRTY_OUT_WARNING,),
            )
        )
    elif made_hand is HandCategory.THREE_OF_A_KIND:
        trip_rank = _ranks_with_count(rank_counts, 3)[0]
        out_ranks = {trip_rank, *[rank for rank, count in rank_counts.items() if count == 1]}
        draws.append(
            Draw(
                draw_type=DrawType.SET_IMPROVEMENT,
                description="Three of a kind can improve to a full house or quads.",
                outs=tuple(card for card in remaining if card.rank in out_ranks),
                warnings=(_DIRTY_OUT_WARNING,),
            )
        )
    return draws


def _is_nut_flush_draw(hero_cards: tuple[Card, ...], suit: Suit) -> bool:
    return any(card.suit is suit and card.rank is Rank.ACE for card in hero_cards)


def _ranks_with_count(rank_counts: Counter[Rank], count: int) -> tuple[Rank, ...]:
    return tuple(rank for rank, actual_count in rank_counts.items() if actual_count == count)


def _straight_out_ranks(rank_values: set[int]) -> set[int]:
    expanded = _ace_low_values(rank_values)
    missing: set[int] = set()
    for start in range(1, 11):
        window = set(range(start, start + 5))
        missing_values = window - expanded
        if len(missing_values) == 1:
            missing.add(_rank_alias(next(iter(missing_values))))
    return missing


def _has_open_ended_shape(rank_values: set[int], out_ranks: set[int]) -> bool:
    expanded = _ace_low_values(rank_values)
    for start in range(1, 12):
        run = set(range(start, start + 4))
        low_out = _rank_alias(start - 1)
        high_out = _rank_alias(start + 4)
        if run.issubset(expanded) and {low_out, high_out}.issubset(out_ranks) and low_out >= 2:
            return True
    return False


def _has_backdoor_straight_shape(rank_values: set[int]) -> bool:
    expanded = _ace_low_values(rank_values)
    return any(len(set(range(start, start + 5)) & expanded) >= 3 for start in range(1, 11))


def _ace_low_values(rank_values: set[int]) -> set[int]:
    values = set(rank_values)
    if 14 in values:
        values.add(1)
    return values


def _rank_alias(rank_value: int) -> int:
    return 14 if rank_value == 1 else rank_value
