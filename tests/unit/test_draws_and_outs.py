"""Tests for draw detection and outs calculation."""

from poker_trainer.engine.draw_detector import DrawType, detect_draws
from poker_trainer.engine.outs_calculator import calculate_outs
from poker_trainer.models import Card, GameState, Position


def cards(codes: str) -> tuple[Card, ...]:
    """Create cards from a whitespace-separated code list."""
    return tuple(Card.from_code(code) for code in codes.split())


def state(hero: str, board: str) -> GameState:
    """Create a test game state."""
    return GameState(
        active_players=2,
        hero_cards=cards(hero),
        community_cards=cards(board),
        hero_position=Position.BUTTON,
    )


def draw_types(game_state: GameState) -> set[DrawType]:
    """Return draw types for a state."""
    return {draw.draw_type for draw in detect_draws(game_state)}


def test_flush_draw_and_nut_flush_draw() -> None:
    draws = detect_draws(state("AS 7S", "QS 2S 9D"))
    flush_draw = next(draw for draw in draws if draw.draw_type is DrawType.FLUSH_DRAW)

    assert flush_draw.is_nut is True
    assert len(flush_draw.outs) == 9


def test_backdoor_flush_draw() -> None:
    draws = detect_draws(state("AS 7D", "QS 2S 9C"))

    assert DrawType.BACKDOOR_FLUSH_DRAW in {draw.draw_type for draw in draws}


def test_open_ended_straight_draw() -> None:
    result = calculate_outs(state("8C 7D", "6S 5H 2C"))

    assert DrawType.OPEN_ENDED_STRAIGHT_DRAW in result.outs_by_draw
    assert len(result.outs_by_draw[DrawType.OPEN_ENDED_STRAIGHT_DRAW]) == 8


def test_gutshot_straight_draw() -> None:
    result = calculate_outs(state("AS KD", "QH 10C 2S"))

    assert DrawType.GUTSHOT_STRAIGHT_DRAW in result.outs_by_draw
    assert {card.rank_value for card in result.outs_by_draw[DrawType.GUTSHOT_STRAIGHT_DRAW]} == {11}


def test_double_gutshot_straight_draw() -> None:
    assert DrawType.DOUBLE_GUTSHOT_STRAIGHT_DRAW in draw_types(state("8C 7D", "5S 9H JC"))


def test_two_overcards() -> None:
    result = calculate_outs(state("AS KH", "QD 7S 2C"))

    assert DrawType.TWO_OVERCARDS in result.outs_by_draw


def test_pair_to_two_pair_or_trips_outs() -> None:
    result = calculate_outs(state("AS AH", "7D 2C 9S"))

    assert DrawType.PAIR_IMPROVEMENT in result.outs_by_draw
    assert len(result.outs_by_draw[DrawType.PAIR_IMPROVEMENT]) == 11


def test_two_pair_to_full_house_outs() -> None:
    result = calculate_outs(state("AS AH", "7D 7C 2S"))

    assert len(result.outs_by_draw[DrawType.TWO_PAIR_IMPROVEMENT]) == 4


def test_set_to_full_house_or_quads_outs() -> None:
    result = calculate_outs(state("AS AH", "AD 7C 2S"))

    assert len(result.outs_by_draw[DrawType.SET_IMPROVEMENT]) == 7


def test_combination_draw_and_unique_out_deduplication() -> None:
    result = calculate_outs(state("AS KS", "QS JS 2C"))
    straight_outs = set(result.outs_by_draw[DrawType.GUTSHOT_STRAIGHT_DRAW])
    flush_outs = set(result.outs_by_draw[DrawType.FLUSH_DRAW])

    assert DrawType.COMBINATION_DRAW in {draw.draw_type for draw in result.draws}
    overcard_outs = set(result.outs_by_draw[DrawType.TWO_OVERCARDS])

    assert len(result.unique_outs) == len(straight_outs | flush_outs | overcard_outs)


def test_no_false_straight_draw_on_completed_straight() -> None:
    types = draw_types(state("AS KD", "QH JC 10S"))

    assert DrawType.GUTSHOT_STRAIGHT_DRAW not in types
    assert DrawType.OPEN_ENDED_STRAIGHT_DRAW not in types


def test_board_only_flush_draw_is_distinguished() -> None:
    draws = detect_draws(state("AH KD", "QS JS 9S 2S"))
    flush_draw = next(draw for draw in draws if draw.draw_type is DrawType.FLUSH_DRAW)

    assert flush_draw.uses_board_only is True


def test_known_cards_excluded_from_outs() -> None:
    result = calculate_outs(state("AS 7S", "QS 2S 9D"))

    assert set(result.unique_outs).isdisjoint(set(cards("AS 7S QS 2S 9D")))
    assert not result.clean_outs
    assert "apparent" in result.limitation.lower()
