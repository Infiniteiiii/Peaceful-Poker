"""Runtime resource lookup for source, installed, and PyInstaller builds."""

import sys
from pathlib import Path

REQUIRED_RESOURCE_NAMES = (
    "Logo.png",
    "Logo.svg",
    "dark.qss",
    "default_settings.json",
    "light.qss",
    "modern.qss",
    "opponent_profiles.json",
    "peaceful_poker.ico",
    "peaceful_poker.svg",
    "recommendation_thresholds.json",
)


def resource_path(name: str) -> Path:
    """Return a bundled Peaceful Poker resource path."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return Path(str(bundle_root)) / "poker_trainer" / "resources" / name
    return Path(__file__).resolve().parent / "resources" / name


def validate_required_resources() -> dict[str, Path]:
    """Return required resources or fail clearly when a build is incomplete."""
    resources = {name: resource_path(name) for name in REQUIRED_RESOURCE_NAMES}
    missing = [name for name, path in resources.items() if not path.is_file()]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Required application resources are missing: {joined}.")
    return resources
