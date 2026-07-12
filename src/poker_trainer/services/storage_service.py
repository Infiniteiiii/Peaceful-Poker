"""Versioned JSON save/load support."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from poker_trainer.models.action_aware import OpponentProfile, TablePlayer, TableState
from poker_trainer.models.card import Card
from poker_trainer.models.game_state import GameState, Position
from poker_trainer.utils.exceptions import (
    InvalidGameStateError,
    StorageError,
    UnsupportedSaveVersionError,
)

SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class SavedHand:
    """Saved hand data with optional notes and analysis summary."""

    game_state: GameState
    opponent_range: str = "random"
    notes: str = ""
    analysis_summary: str | None = None
    source_schema_version: int = SCHEMA_VERSION


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
    if version not in {1, SCHEMA_VERSION}:
        raise UnsupportedSaveVersionError(f"Unsupported save schema version: {version!r}.")
    try:
        table_state = (
            _table_from_payload(payload["table_state"]) if version == SCHEMA_VERSION else None
        )
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
            table_state=table_state,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise StorageError("Save file is missing required hand fields.") from exc
    return SavedHand(
        game_state=state,
        opponent_range=str(payload.get("opponent_range", "random")),
        notes=str(payload.get("notes", "")),
        analysis_summary=payload.get("analysis_summary"),
        source_schema_version=int(version),
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
        "table_state": _table_to_payload(state.table_state),
    }


def _cards(values: object) -> tuple[Card, ...]:
    if not isinstance(values, list):
        raise StorageError("Card fields must be JSON lists.")
    return tuple(Card.from_code(str(value)) for value in values)


def _table_to_payload(table_state: TableState | None) -> dict[str, Any] | None:
    if table_state is None:
        return None
    return {
        "button_seat": table_state.button_seat,
        "small_blind_seat": table_state.small_blind_seat,
        "big_blind_seat": table_state.big_blind_seat,
        "hero_seat": table_state.hero_seat,
        "current_actor_seat": table_state.current_actor_seat,
        "street": table_state.street,
        "players": [
            {
                "seat": player.seat,
                "position": player.position,
                "is_hero": player.is_hero,
                "dealt_in": player.dealt_in,
                "folded": player.folded,
                "all_in": player.all_in,
                "stack": player.stack,
                "round_contribution": player.round_contribution,
                "total_contribution": player.total_contribution,
                "profile": player.profile.value,
                "range_text": player.range_text,
                "previous_actions": list(player.previous_actions),
                "eligible_to_act": player.eligible_to_act,
                "acted_this_round": player.acted_this_round,
            }
            for player in table_state.players
        ],
    }


def _table_from_payload(value: object) -> TableState:
    if not isinstance(value, dict):
        raise StorageError("Schema version 2 requires a table_state object.")
    players_value = value.get("players")
    if not isinstance(players_value, list):
        raise StorageError("Table state players must be a JSON list.")
    players: list[TablePlayer] = []
    for player_value in players_value:
        if not isinstance(player_value, dict):
            raise StorageError("Each table player must be a JSON object.")
        actions = player_value.get("previous_actions", [])
        if not isinstance(actions, list):
            raise StorageError("Previous actions must be a JSON list.")
        try:
            players.append(
                TablePlayer(
                    seat=int(player_value["seat"]),
                    position=str(player_value["position"]),
                    is_hero=bool(player_value.get("is_hero", False)),
                    dealt_in=bool(player_value.get("dealt_in", True)),
                    folded=bool(player_value.get("folded", False)),
                    all_in=bool(player_value.get("all_in", False)),
                    stack=float(player_value.get("stack", 0.0)),
                    round_contribution=float(player_value.get("round_contribution", 0.0)),
                    total_contribution=float(player_value.get("total_contribution", 0.0)),
                    profile=OpponentProfile(
                        str(player_value.get("profile", OpponentProfile.UNKNOWN_BALANCED.value))
                    ),
                    range_text=str(player_value.get("range_text", "random")),
                    previous_actions=tuple(str(action) for action in actions),
                    eligible_to_act=bool(player_value.get("eligible_to_act", True)),
                    acted_this_round=bool(player_value.get("acted_this_round", False)),
                )
            )
        except (InvalidGameStateError, KeyError, TypeError, ValueError) as exc:
            raise StorageError("Table player contains invalid or missing fields.") from exc
    try:
        return TableState(
            players=tuple(players),
            button_seat=int(value["button_seat"]),
            small_blind_seat=int(value["small_blind_seat"]),
            big_blind_seat=int(value["big_blind_seat"]),
            hero_seat=int(value["hero_seat"]),
            current_actor_seat=int(value["current_actor_seat"]),
            street=str(value["street"]),
        )
    except (InvalidGameStateError, KeyError, TypeError, ValueError) as exc:
        raise StorageError("Table state contains invalid or missing fields.") from exc
