import os
import sys
from pathlib import Path

# Ensure Qt finds the bundled platform plugins when tests run.
# This must be set before pytest-qt creates the QApplication instance.
QT_PLATFORM = os.environ.get("QT_QPA_PLATFORM")
if not QT_PLATFORM:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

if "QT_QPA_PLATFORM_PLUGIN_PATH" not in os.environ:
    python_dir = Path(sys.executable).resolve().parent
    venv_dir = python_dir.parent
    plugin_path = (
        venv_dir
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
        / "PySide6"
        / "Qt"
        / "plugins"
        / "platforms"
    )
    if plugin_path.exists():
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugin_path)

# Optional debug flag to show why Qt plugin loading fails.
if "QT_DEBUG_PLUGINS" not in os.environ:
    os.environ["QT_DEBUG_PLUGINS"] = "1"
