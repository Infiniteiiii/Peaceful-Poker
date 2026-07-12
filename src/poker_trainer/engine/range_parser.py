"""Opponent range presets and a practical subset of range notation."""

from itertools import combinations

from poker_trainer.models.card import Card, Rank
from poker_trainer.utils.exceptions import UnsupportedRangeError

RankPair = tuple[Rank, Rank]
CardCombo = tuple[Card, Card]

_RANK_ORDER = tuple(Rank)
_RANK_BY_CODE = {rank.short_code: rank for rank in Rank}
_RANK_BY_CODE["10"] = Rank.TEN
_PRESET_NAMES = {"random", "any two", "tight", "standard", "loose", "premium"}


def available_combinations(cards: tuple[Card, ...]) -> tuple[CardCombo, ...]:
    """Return all two-card combinations from available cards."""
    return tuple((first, second) for first, second in combinations(cards, 2))


def filter_combinations(combos: tuple[CardCombo, ...], range_text: str) -> tuple[CardCombo, ...]:
    """Filter card combinations using a preset or supported notation subset."""
    normalized = range_text.strip().lower()
    if normalized in {"", "random", "any two"}:
        return combos
    if normalized in _PRESET_NAMES:
        return _filter_preset(combos, normalized)

    accepted: list[CardCombo] = []
    for token in (part.strip() for part in range_text.split(",")):
        if not token:
            continue
        accepted.extend(combo for combo in combos if _matches_token(combo, token.upper()))
    if not accepted:
        raise UnsupportedRangeError(f"Unsupported or empty opponent range: {range_text!r}.")
    return tuple(dict.fromkeys(accepted))


def _filter_preset(combos: tuple[CardCombo, ...], preset: str) -> tuple[CardCombo, ...]:
    if preset == "premium":
        return tuple(
            combo for combo in combos if _is_pair_at_least(combo, Rank.QUEEN) or _is_big_ace(combo)
        )
    if preset == "tight":
        return tuple(
            combo
            for combo in combos
            if _is_pair_at_least(combo, Rank.NINE) or _high_cards(combo, 12)
        )
    if preset == "standard":
        return tuple(
            combo
            for combo in combos
            if _is_pair_at_least(combo, Rank.SEVEN) or _high_cards(combo, 10)
        )
    if preset == "loose":
        return tuple(
            combo for combo in combos if _is_pair_at_least(combo, Rank.TWO) or _high_cards(combo, 8)
        )
    return combos


def _matches_token(combo: CardCombo, token: str) -> bool:
    if "+" in token and "-" in token:
        raise UnsupportedRangeError(f"Unsupported mixed range token: {token!r}.")
    if "-" in token:
        return _matches_pair_interval(combo, token)
    if token.endswith("+"):
        return _matches_plus(combo, token[:-1])
    return _matches_exact(combo, token)


def _matches_exact(combo: CardCombo, token: str) -> bool:
    ranks = _sorted_ranks(combo)
    suited = combo[0].suit is combo[1].suit
    if len(token) == 2 and token[0] == token[1]:
        rank = _rank(token[0])
        return ranks == (rank, rank)
    if len(token) == 3 and token[2] in {"S", "O"}:
        high, low = _rank(token[0]), _rank(token[1])
        if ranks != _descending_pair(high, low):
            return False
        return suited if token[2] == "S" else not suited
    raise UnsupportedRangeError(f"Unsupported range token: {token!r}.")


def _matches_plus(combo: CardCombo, base: str) -> bool:
    ranks = _sorted_ranks(combo)
    if len(base) == 2 and base[0] == base[1]:
        rank = _rank(base[0])
        return ranks[0] == ranks[1] and ranks[0] >= rank
    if len(base) == 3 and base[2] in {"S", "O"}:
        high, low = _rank(base[0]), _rank(base[1])
        suited = combo[0].suit is combo[1].suit
        return ranks[0] == high and ranks[1] >= low and (suited if base[2] == "S" else not suited)
    raise UnsupportedRangeError(f"Unsupported plus range token: {base + '+'!r}.")


def _matches_pair_interval(combo: CardCombo, token: str) -> bool:
    start_text, end_text = token.split("-", 1)
    if (
        len(start_text) != 2
        or len(end_text) != 2
        or start_text[0] != start_text[1]
        or end_text[0] != end_text[1]
    ):
        raise UnsupportedRangeError(f"Only pair intervals like 22-88 are supported: {token!r}.")
    start = _rank(start_text[0])
    end = _rank(end_text[0])
    low, high = sorted((start, end))
    ranks = _sorted_ranks(combo)
    return ranks[0] == ranks[1] and low <= ranks[0] <= high


def _rank(code: str) -> Rank:
    try:
        return _RANK_BY_CODE[code]
    except KeyError as exc:
        raise UnsupportedRangeError(f"Unsupported rank in range token: {code!r}.") from exc


def _sorted_ranks(combo: CardCombo) -> RankPair:
    first, second = combo[0].rank, combo[1].rank
    return _descending_pair(first, second)


def _descending_pair(first: Rank, second: Rank) -> RankPair:
    return (first, second) if first >= second else (second, first)


def _is_pair_at_least(combo: CardCombo, rank: Rank) -> bool:
    return combo[0].rank == combo[1].rank and combo[0].rank >= rank


def _is_big_ace(combo: CardCombo) -> bool:
    ranks = {combo[0].rank, combo[1].rank}
    return Rank.ACE in ranks and any(rank >= Rank.KING for rank in ranks if rank is not Rank.ACE)


def _high_cards(combo: CardCombo, minimum: int) -> bool:
    return combo[0].rank_value >= minimum and combo[1].rank_value >= minimum
