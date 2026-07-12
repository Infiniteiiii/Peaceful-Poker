"""Command-line entry point for the desktop application shell."""

from poker_trainer.app import run


def main() -> int:
    """Run the Peaceful Poker application."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
