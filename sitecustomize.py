"""Local startup tweaks for running Peaceful Poker from the repo root."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

plugin_root = (
    Path(sys.prefix)
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
    / "PySide6"
    / "Qt"
    / "plugins"
)
platform_plugins = plugin_root / "platforms"
os.environ.setdefault("QT_PLUGIN_PATH", str(plugin_root))
os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(platform_plugins))
