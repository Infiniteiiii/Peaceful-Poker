"""Local startup tweaks for running Peaceful Poker from the repo root."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    import PySide6

    pyside_root = Path(PySide6.__file__).resolve().parent
    plugin_root = pyside_root / "plugins"
    platform_plugins = plugin_root / "platforms"

    if plugin_root.is_dir():
        os.environ["QT_PLUGIN_PATH"] = str(plugin_root)

    if platform_plugins.is_dir():
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_plugins)
except ImportError:
    pass
