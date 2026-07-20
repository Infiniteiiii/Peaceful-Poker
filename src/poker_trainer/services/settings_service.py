"""Persistent user settings."""

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from poker_trainer.resource_path import resource_path
from poker_trainer.services.storage_service import user_data_dir
from poker_trainer.utils.exceptions import StorageError


@dataclass(frozen=True, slots=True)
class UserSettings:
    """Persistent application settings."""

    theme: str = "light"
    advanced_mode: bool = False
    automatic_analysis: bool = False
    default_player_count: int = 6
    default_simulation_count: int = 25_000
    percentage_precision: int = 1
    detailed_explanations: bool = True
    small_blind: float = 1.0
    big_blind: float = 2.0
    window_geometry: str | None = None

    def __post_init__(self) -> None:
        if self.theme not in {"light", "dark"}:
            raise StorageError("Theme must be 'light' or 'dark'.")
        if not 2 <= self.default_player_count <= 10:
            raise StorageError("Default player count must be from 2 through 10.")
        if self.default_simulation_count <= 0:
            raise StorageError("Default simulation count must be positive.")
        if not 0 <= self.percentage_precision <= 4:
            raise StorageError("Percentage precision must be from 0 through 4.")
        if self.small_blind < 0 or self.big_blind < 0 or self.small_blind > self.big_blind:
            raise StorageError("Default blinds must be nonnegative and ordered.")


def settings_path() -> Path:
    """Return the settings JSON path."""
    return user_data_dir() / "settings.json"


def load_settings(path: Path | None = None) -> UserSettings:
    """Load user settings or return defaults."""
    target = path or settings_path()
    if not target.exists():
        return default_settings()
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


@lru_cache(maxsize=1)
def default_settings() -> UserSettings:
    """Load packaged defaults, falling back to dataclass defaults if unavailable."""
    try:
        payload = json.loads(resource_path("default_settings.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UserSettings()
    if not isinstance(payload, dict):
        return UserSettings()
    return UserSettings(**_known_settings(payload))
