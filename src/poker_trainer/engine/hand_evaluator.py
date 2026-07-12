"""Custom Texas Hold'em hand evaluator."""

from collections import Counter
from collections.abc import Iterable
from itertools import combinations

from poker_trainer.models.card import Card, Rank
from poker_trainer.models.hand import EvaluatedHand, HandCategory
from poker_trainer.utils.exceptions import DuplicateCardError, InvalidHandError


def evaluate_best_hand(cards: Iterable[Card]) -> EvaluatedHand:
    """Return the strongest five-card poker hand from five to seven cards."""
    card_tuple = tuple(cards)
    _validate_unique_cards(card_tuple)
    if not 5 <= len(card_tuple) <= 7:
        raise InvalidHandError("Best-hand evaluation requires between five and seven cards.")

    return max(evaluate_five_card_hand(combo) for combo in combinations(card_tuple, 5))


def evaluate_five_card_hand(cards: Iterable[Card]) -> EvaluatedHand:
    """Evaluate exactly five cards."""
    card_tuple = tuple(cards)
    _validate_unique_cards(card_tuple)
    if len(card_tuple) != 5:
        raise InvalidHandError("Five-card evaluation requires exactly five cards.")

    rank_counts = Counter(card.rank_value for card in card_tuple)
    ranks_desc = tuple(sorted(rank_counts, reverse=True))
    counts_desc = sorted(rank_counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    flush = len({card.suit for card in card_tuple}) == 1
    straight_high = _straight_high(rank_counts)

    if flush and straight_high is not None:
        return _build_hand(
            HandCategory.STRAIGHT_FLUSH,
            (straight_high,),
            card_tuple,
            _straight_description(straight_high, flush=True),
        )

    if counts_desc[0][1] == 4:
        quad_rank = counts_desc[0][0]
        kicker = max(rank for rank in rank_counts if rank != quad_rank)
        return _build_hand(
            HandCategory.FOUR_OF_A_KIND,
            (quad_rank, kicker),
            card_tuple,
            f"Four of a kind, {_plural_rank_name(quad_rank)}, with a {_rank_name(kicker)} kicker",
        )

    if [count for _, count in counts_desc] == [3, 2]:
        trip_rank, pair_rank = counts_desc[0][0], counts_desc[1][0]
        return _build_hand(
            HandCategory.FULL_HOUSE,
            (trip_rank, pair_rank),
            card_tuple,
            f"Full house, {_plural_rank_name(trip_rank)} full of {_plural_rank_name(pair_rank)}",
        )

    if flush:
        return _build_hand(
            HandCategory.FLUSH,
            ranks_desc,
            card_tuple,
            f"Flush, {_rank_name(ranks_desc[0])} high",
        )

    if straight_high is not None:
        return _build_hand(
            HandCategory.STRAIGHT,
            (straight_high,),
            card_tuple,
            _straight_description(straight_high, flush=False),
        )

    if counts_desc[0][1] == 3:
        trip_rank = counts_desc[0][0]
        kickers = tuple(sorted((rank for rank in rank_counts if rank != trip_rank), reverse=True))
        return _build_hand(
            HandCategory.THREE_OF_A_KIND,
            (trip_rank, *kickers),
            card_tuple,
            f"Three of a kind, {_plural_rank_name(trip_rank)}, with "
            f"{_join_rank_names(kickers)} kickers",
        )

    pair_ranks = tuple(
        sorted((rank for rank, count in rank_counts.items() if count == 2), reverse=True)
    )
    if len(pair_ranks) == 2:
        kicker = max(rank for rank, count in rank_counts.items() if count == 1)
        return _build_hand(
            HandCategory.TWO_PAIR,
            (*pair_ranks, kicker),
            card_tuple,
            f"Two pair, {_plural_rank_name(pair_ranks[0])} and "
            f"{_plural_rank_name(pair_ranks[1])}, with a {_rank_name(kicker)} kicker",
        )

    if len(pair_ranks) == 1:
        pair_rank = pair_ranks[0]
        kickers = tuple(sorted((rank for rank in rank_counts if rank != pair_rank), reverse=True))
        return _build_hand(
            HandCategory.PAIR,
            (pair_rank, *kickers),
            card_tuple,
            f"One pair, {_plural_rank_name(pair_rank)}, with {_join_rank_names(kickers)} kickers",
        )

    return _build_hand(
        HandCategory.HIGH_CARD,
        ranks_desc,
        card_tuple,
        f"High card, {_rank_name(ranks_desc[0])}",
    )


def _validate_unique_cards(cards: tuple[Card, ...]) -> None:
    if len(set(cards)) != len(cards):
        raise DuplicateCardError("A card cannot appear more than once in the same hand.")


def _straight_high(rank_counts: Counter[int]) -> int | None:
    unique = set(rank_counts)
    if Rank.ACE in unique:
        unique.add(1)

    for high in range(14, 4, -1):
        needed = {high - offset for offset in range(5)}
        if needed.issubset(unique):
            return high
    return None


def _build_hand(
    category: HandCategory,
    tie_breakers: tuple[int, ...],
    cards: tuple[Card, ...],
    description: str,
) -> EvaluatedHand:
    return EvaluatedHand(
        category=category,
        tie_breakers=tie_breakers,
        cards=_display_order(cards, category, tie_breakers),
        description=description,
    )


def _display_order(
    cards: tuple[Card, ...],
    category: HandCategory,
    tie_breakers: tuple[int, ...],
) -> tuple[Card, ...]:
    if category in {HandCategory.STRAIGHT, HandCategory.STRAIGHT_FLUSH} and tie_breakers == (5,):
        order = {5: 0, 4: 1, 3: 2, 2: 3, 14: 4}
        return tuple(sorted(cards, key=lambda card: (order[card.rank_value], card.suit.code)))
    return tuple(sorted(cards, key=lambda card: (card.rank_value, card.suit.code), reverse=True))


def _rank_name(rank_value: int) -> str:
    return Rank(rank_value).display_name


def _plural_rank_name(rank_value: int) -> str:
    return Rank(rank_value).plural_name


def _join_rank_names(rank_values: tuple[int, ...]) -> str:
    names = [_rank_name(rank) for rank in rank_values]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def _straight_description(high_card: int, *, flush: bool) -> str:
    if high_card == 14 and flush:
        return "Royal Flush"
    category = "Straight flush" if flush else "Straight"
    return f"{category}, {_rank_name(high_card)} high"
