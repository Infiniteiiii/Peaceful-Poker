"""File watcher for hot-reloading UI changes during development."""

# ruff: noqa: I001

from collections.abc import Callable
from pathlib import Path
import time
from typing import Any, TYPE_CHECKING

# `watchdog` is an optional development dependency. At type-check time we
# avoid importing `watchdog` (which may not be installed) and instead use
# plain `Any` types so static checks succeed. At runtime we attempt to
# import the real classes and fall back to trivial stand-ins when not
# available.
if TYPE_CHECKING:
    FileModifiedEvent: Any
    FileSystemEventHandler: Any
    Observer: Any
else:
    try:
        from watchdog.events import FileModifiedEvent, FileSystemEventHandler  # type: ignore
        from watchdog.observers import Observer  # type: ignore
    except Exception:  # pragma: no cover - optional dev dependency
        FileModifiedEvent = object  # type: ignore
        FileSystemEventHandler = object  # type: ignore
        Observer = object  # type: ignore


class UIFileHandler:
    """Watch UI files and trigger reload on change.

    We intentionally do not subclass `FileSystemEventHandler` because
    `watchdog` is an optional dev dependency and may not be available
    at type-check or runtime. The Observer only requires an object with
    the expected handler methods (e.g., `on_modified`), so a plain
    class is sufficient and avoids mypy subclassing issues.
    """

    def __init__(self, callback: Callable[[], None], watch_paths: list[str]) -> None:
        self.callback = callback
        self.watch_paths = watch_paths
        # Use float for timestamps (ms) to match time.time() * 1000
        self.last_trigger: float = 0.0
        self.debounce_ms = 500

    def on_modified(self, event: Any) -> None:
        """Trigger callback on UI file modification."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only watch .py and .qss files
        if file_path.suffix not in (".py", ".qss"):
            return

        # Debounce: ignore rapid repeated saves
        now = time.time() * 1000
        if now - self.last_trigger < self.debounce_ms:
            return

        self.last_trigger = now
        print(f"[HOT RELOAD] Detected change: {file_path.name}")
        self.callback()


def start_hot_reload_watcher(callback: Callable[[], None], ui_dir: Path) -> Any:
    """Start file watcher for UI directory."""
    observer = Observer()
    handler = UIFileHandler(callback, [str(ui_dir)])
    observer.schedule(handler, str(ui_dir), recursive=True)
    observer.start()
    print(f"[HOT RELOAD] Watching {ui_dir} for changes...")
    return observer
