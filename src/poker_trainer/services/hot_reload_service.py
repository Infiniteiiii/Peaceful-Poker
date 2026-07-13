"""File watcher for hot-reloading UI changes during development."""

import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer


class UIFileHandler(FileSystemEventHandler):
    """Watch UI files and trigger reload on change."""

    def __init__(self, callback: Callable[[], None], watch_paths: list[str]) -> None:
        self.callback = callback
        self.watch_paths = watch_paths
        self.last_trigger = 0
        self.debounce_ms = 500

    def on_modified(self, event: FileModifiedEvent) -> None:
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


def start_hot_reload_watcher(
    callback: Callable[[], None], ui_dir: Path
) -> Observer:
    """Start file watcher for UI directory."""
    observer = Observer()
    handler = UIFileHandler(callback, [str(ui_dir)])
    observer.schedule(handler, str(ui_dir), recursive=True)
    observer.start()
    print(f"[HOT RELOAD] Watching {ui_dir} for changes...")
    return observer
