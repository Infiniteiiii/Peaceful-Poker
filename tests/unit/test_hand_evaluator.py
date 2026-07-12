"""Tests for five-card and seven-card poker evaluation."""

import pytest

from poker_trainer.engine import evaluate_best_hand, evaluate_five_card_hand
from poker_trainer.models import Card, HandCategory
from poker_trainer.utils.exceptions import DuplicateCardError, InvalidHandError


def cards(codes: str) -> list[Card]:
    """Create cards from a whitespace-separated code list."""
    return [Card.from_code(code) for code in codes.split()]


@pytest.mark.parametrize(
    ("codes", "category", "tie_breakers", "display_category"),
    [
        ("AS KS QS JS 10S", HandCategory.STRAIGHT_FLUSH, (14,), "Royal Flush"),
        ("KS QS JS 10S 9S", HandCategory.STRAIGHT_FLUSH, (13,), "Straight Flush"),
        ("AS AH AD AC 2S", HandCategory.FOUR_OF_A_KIND, (14, 2), "Four of a Kind"),
        ("KH KC KD 7S 7D", HandCategory.FULL_HOUSE, (13, 7), "Full House"),
        ("AS JS 8S 4S 2S", HandCategory.FLUSH, (14, 11, 8, 4, 2), "Flush"),
        ("AS 2D 3C 4H 5S", HandCategory.STRAIGHT, (5,), "Straight"),
        ("9S 9H 9D KC 2S", HandCategory.THREE_OF_A_KIND, (9, 13, 2), "Three of a Kind"),
        ("KS KH 7S 7D AH", HandCategory.TWO_PAIR, (13, 7, 14), "Two Pair"),
        ("QS QH AS 9D 3C", HandCategory.PAIR, (12, 14, 9, 3), "One Pair"),
        ("AS KD 9H 5C 2D", HandCategory.HIGH_CARD, (14, 13, 9, 5, 2), "High Card"),
    ],
)
def test_evaluates_all_five_card_categories(
    codes: str,
    category: HandCategory,
    tie_breakers: tuple[int, ...],
    display_category: str,
) -> None:
    hand = evaluate_five_card_hand(cards(codes))

    assert hand.category is category
    assert hand.tie_breakers == tie_breakers
    assert hand.display_category == display_category


def test_ace_low_straight_is_five_high() -> None:
    hand = evaluate_five_card_hand(cards("AS 2D 3C 4H 5S"))

    assert hand.tie_breakers == (5,)
    assert [card.rank_value for card in hand.cards] == [5, 4, 3, 2, 14]


def test_best_hand_from_seven_cards_selects_strongest_combination() -> None:
    hand = evaluate_best_hand(cards("AS KS QS JS 10S 2C 2D"))

    assert hand.display_category == "Royal Flush"
    assert [card.code for card in hand.cards] == ["AS", "KS", "QS", "JS", "10S"]


def test_best_full_house_uses_highest_available_trips_and_pair() -> None:
    hand = evaluate_best_hand(cards("AS AH AD KC KH KS 2D"))

    assert hand.category is HandCategory.FULL_HOUSE
    assert hand.tie_breakers == (14, 13)


def test_pair_tie_breakers_compare_kickers_in_order() -> None:
    stronger = evaluate_five_card_hand(cards("AS AH KD QS 2C"))
    weaker = evaluate_five_card_hand(cards("AS AH JD 10S 9C"))

    assert stronger > weaker


def test_two_pair_tie_breakers_compare_higher_pair_then_lower_pair_then_kicker() -> None:
    stronger_kicker = evaluate_five_card_hand(cards("KS KH 7S 7D AS"))
    weaker_kicker = evaluate_five_card_hand(cards("KS KH 7S 7D QS"))
    stronger_lower_pair = evaluate_five_card_hand(cards("KS KH 8S 8D 2C"))

    assert stronger_kicker > weaker_kicker
    assert stronger_lower_pair > stronger_kicker


def test_straight_comparison_handles_wheel_correctly() -> None:
    wheel = evaluate_five_card_hand(cards("AS 2D 3C 4H 5S"))
    six_high = evaluate_five_card_hand(cards("2S 3D 4C 5H 6S"))

    assert six_high > wheel


def test_exact_split_scores_compare_equal() -> None:
    first = evaluate_five_card_hand(cards("AS KD QH JC 9S"))
    second = evaluate_five_card_hand(cards("AD KC QS JH 9D"))

    assert first.score == second.score


def test_duplicate_cards_are_rejected() -> None:
    with pytest.raises(DuplicateCardError):
        evaluate_five_card_hand(cards("AS AS KD QH JC"))


def test_best_hand_requires_five_to_seven_cards() -> None:
    with pytest.raises(InvalidHandError):
        evaluate_best_hand(cards("AS KD QH JC"))
