"""Tests for standard deck behavior."""

import pytest

from poker_trainer.models import Card, Deck
from poker_trainer.utils.exceptions import DuplicateCardError


def test_standard_deck_contains_52_unique_cards() -> None:
    deck = Deck.standard()

    assert len(deck) == 52
    assert len(set(deck.cards)) == 52


def test_remove_known_cards() -> None:
    deck = Deck.standard()
    cards = [Card.from_code("AS"), Card.from_code("KH"), Card.from_code("2C")]

    deck.remove_many(cards)

    assert len(deck) == 49
    assert all(card not in deck for card in cards)


def test_duplicate_known_card_is_rejected() -> None:
    deck = Deck.standard()
    card = Card.from_code("AS")

    with pytest.raises(DuplicateCardError):
        deck.remove_many([card, card])


def test_draw_removes_cards_from_top() -> None:
    deck = Deck.standard()

    drawn = deck.draw(2)

    assert len(drawn) == 2
    assert len(deck) == 50
    assert all(card not in deck for card in drawn)
