"""Versioned JSON save/load support."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from poker_trainer.models.card import Card
from poker_trainer.models.game_state import GameState, Position
from poker_trainer.utils.exceptions import StorageError, UnsupportedSaveVersionError

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SavedHand:
    """Saved hand data with optional notes and analysis summary."""

    game_state: GameState
    opponent_range: str = "random"
    notes: str = ""
    analysis_summary: str | None = None


def user_data_dir() -> Path:
    """Return the local Peaceful Poker data directory."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "Peaceful Poker"


def save_hand(saved_hand: SavedHand, path: Path | None = None) -> Path:
    """Save a hand as versioned JSON."""
    target = path or user_data_dir() / "hands" / "last_hand.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_to_payload(saved_hand), indent=2), encoding="utf-8")
    return target


def load_hand(path: Path) -> SavedHand:
    """Load and validate a saved hand JSON file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StorageError(f"Invalid JSON save file: {path}.") from exc
    if not isinstance(payload, dict):
        raise StorageError("Save file must contain a JSON object.")
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise UnsupportedSaveVersionError(f"Unsupported save schema version: {version!r}.")
    try:
        state = GameState(
            active_players=int(payload["active_players"]),
            hero_cards=_cards(payload["hero_cards"]),
            community_cards=_cards(payload["community_cards"]),
            hero_position=Position(str(payload["hero_position"])),
            pot_size=float(payload["pot_size"]),
            amount_to_call=float(payload["amount_to_call"]),
            hero_stack=float(payload["hero_stack"]),
            effective_stack=float(payload["effective_stack"]),
            small_blind=float(payload["small_blind"]),
            big_blind=float(payload["big_blind"]),
            ante=float(payload["ante"]),
            previous_action=payload.get("previous_action"),
            requested_simulation_count=int(payload["requested_simulation_count"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise StorageError("Save file is missing required hand fields.") from exc
    return SavedHand(
        game_state=state,
        opponent_range=str(payload.get("opponent_range", "random")),
        notes=str(payload.get("notes", "")),
        analysis_summary=payload.get("analysis_summary"),
    )


def duplicate_hand(source: Path, destination: Path) -> Path:
    """Duplicate a saved hand after validating the source."""
    hand = load_hand(source)
    return save_hand(hand, destination)


def _to_payload(saved_hand: SavedHand) -> dict[str, Any]:
    state = saved_hand.game_state
    return {
        "schema_version": SCHEMA_VERSION,
        "game_type": "no_limit_texas_holdem",
        "active_players": state.active_players,
        "hero_cards": [card.code for card in state.hero_cards],
        "community_cards": [card.code for card in state.community_cards],
        "hero_position": state.hero_position.value,
        "pot_size": state.pot_size,
        "amount_to_call": state.amount_to_call,
        "hero_stack": state.hero_stack,
        "effective_stack": state.effective_stack,
        "small_blind": state.small_blind,
        "big_blind": state.big_blind,
        "ante": state.ante,
        "previous_action": state.previous_action,
        "requested_simulation_count": state.requested_simulation_count,
        "opponent_range": saved_hand.opponent_range,
        "notes": saved_hand.notes,
        "analysis_summary": saved_hand.analysis_summary,
    }


def _cards(values: object) -> tuple[Card, ...]:
    if not isinstance(values, list):
        raise StorageError("Card fields must be JSON lists.")
    return tuple(Card.from_code(str(value)) for value in values)
