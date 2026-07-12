"""Persistent user settings."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from poker_trainer.services.storage_service import user_data_dir
from poker_trainer.utils.exceptions import StorageError


@dataclass(frozen=True, slots=True)
class UserSettings:
    """Persistent application settings."""

    theme: str = "light"
    automatic_analysis: bool = False
    default_player_count: int = 6
    default_simulation_count: int = 25_000
    percentage_precision: int = 1
    detailed_explanations: bool = True
    small_blind: float = 1.0
    big_blind: float = 2.0
    window_geometry: str | None = None


def settings_path() -> Path:
    """Return the settings JSON path."""
    return user_data_dir() / "settings.json"


def load_settings(path: Path | None = None) -> UserSettings:
    """Load user settings or return defaults."""
    target = path or settings_path()
    if not target.exists():
        return UserSettings()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StorageError("Settings file contains invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise StorageError("Settings file must contain a JSON object.")
    return UserSettings(**_known_settings(payload))


def save_settings(settings: UserSettings, path: Path | None = None) -> Path:
    """Persist user settings as readable JSON."""
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return target


def _known_settings(payload: dict[str, Any]) -> dict[str, Any]:
    names = set(UserSettings.__dataclass_fields__)
    return {key: value for key, value in payload.items() if key in names}
