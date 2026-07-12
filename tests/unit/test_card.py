"""Tests for card parsing and display behavior."""

import pytest

from poker_trainer.models import Card, Rank, Suit
from poker_trainer.utils.exceptions import InvalidCardError


def test_card_from_code_accepts_canonical_and_ten_alias() -> None:
    assert Card.from_code("AS") == Card(Rank.ACE, Suit.SPADES)
    assert Card.from_code("10h") == Card(Rank.TEN, Suit.HEARTS)
    assert Card.from_code("td") == Card(Rank.TEN, Suit.DIAMONDS)


def test_card_exposes_display_and_numeric_values() -> None:
    card = Card.from_code("QC")

    assert card.code == "QC"
    assert card.short_code == "QC"
    assert card.display_name == "Queen of Clubs"
    assert card.rank_value == 12


@pytest.mark.parametrize("code", ["", "1S", "11H", "AX", "Spades", "Q"])
def test_invalid_card_codes_raise_clear_error(code: str) -> None:
    with pytest.raises(InvalidCardError):
        Card.from_code(code)
