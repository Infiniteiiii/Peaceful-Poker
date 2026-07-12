"""Runtime resource lookup for source, installed, and PyInstaller builds."""

import sys
from pathlib import Path


def resource_path(name: str) -> Path:
    """Return a bundled Peaceful Poker resource path."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return Path(str(bundle_root)) / "poker_trainer" / "resources" / name
    return Path(__file__).resolve().parent / "resources" / name
