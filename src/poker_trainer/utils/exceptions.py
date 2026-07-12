"""Custom exceptions for clear domain errors."""


class PokerTrainerError(Exception):
    """Base class for application-specific errors."""


class InvalidCardError(PokerTrainerError):
    """Raised when a card code or card value is invalid."""


class DuplicateCardError(PokerTrainerError):
    """Raised when a card is selected more than once."""


class InvalidHandError(PokerTrainerError):
    """Raised when a hand cannot be evaluated."""


class InvalidGameStateError(PokerTrainerError):
    """Raised when the entered game state is impossible."""


class InvalidBoardLengthError(InvalidGameStateError):
    """Raised when community-card count cannot form a valid Hold'em street."""


class InvalidBetError(PokerTrainerError):
    """Raised when betting information is invalid."""


class UnsupportedExactCalculationError(PokerTrainerError):
    """Raised when exact enumeration is intentionally unsupported for a state."""


class UnsupportedRangeError(PokerTrainerError):
    """Raised when an opponent range is malformed or unsupported."""


class SimulationCancelledError(PokerTrainerError):
    """Raised when an in-progress simulation is cancelled."""


class InsufficientInformationError(PokerTrainerError):
    """Raised when advice requires more information than was entered."""


class StorageError(PokerTrainerError):
    """Raised when saved hand data cannot be loaded or written."""


class UnsupportedSaveVersionError(StorageError):
    """Raised when a save file has a future or unsupported schema version."""
