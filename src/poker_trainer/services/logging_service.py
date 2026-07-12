"""Application logging setup."""

import logging
from pathlib import Path

from poker_trainer.services.storage_service import user_data_dir


def configure_logging(path: Path | None = None) -> Path:
    """Configure file logging and return the log path."""
    log_path = path or user_data_dir() / "logs" / "peaceful_poker.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger(__name__).info("Peaceful Poker logging configured.")
    return log_path
