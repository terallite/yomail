"""Exceptions for yomail email body extraction."""

from dataclasses import dataclass


class ExtractionError(Exception):
    """Base exception for all extraction errors."""

    pass


@dataclass
class InvalidInputError(ExtractionError):
    """Input is not valid for processing.

    Raised when:
    - Input is empty or becomes empty after normalization
    - Input is not valid text
    """

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class NoBodyDetectedError(ExtractionError):
    """No body content could be detected in the email."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class LowConfidenceError(ExtractionError):
    """Extraction confidence is below the threshold.

    Attributes:
        message: Description of the error.
        confidence: The computed confidence score.
        threshold: The required threshold.
    """

    message: str
    confidence: float
    threshold: float

    def __str__(self) -> str:
        return f"{self.message} (confidence: {self.confidence:.2f}, threshold: {self.threshold:.2f})"
