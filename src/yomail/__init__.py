"""yomail - Extract body text from Japanese business emails."""

from yomail.exceptions import (
    ExtractionError,
    InvalidInputError,
    LowConfidenceError,
    NoBodyDetectedError,
)
from yomail.pipeline import NormalizedEmail, Normalizer

__version__ = "0.1.0"

__all__ = [
    "ExtractionError",
    "InvalidInputError",
    "LowConfidenceError",
    "NoBodyDetectedError",
    "NormalizedEmail",
    "Normalizer",
]
