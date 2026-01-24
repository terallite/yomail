"""yomail - Extract body text from Japanese business emails."""

from yomail.exceptions import (
    ExtractionError,
    InvalidInputError,
    LowConfidenceError,
    NoBodyDetectedError,
)
from yomail.pipeline import (
    AnnotatedLine,
    NormalizedEmail,
    Normalizer,
    StructuralAnalysis,
    StructuralAnalyzer,
)

__version__ = "0.1.0"

__all__ = [
    "AnnotatedLine",
    "ExtractionError",
    "InvalidInputError",
    "LowConfidenceError",
    "NoBodyDetectedError",
    "NormalizedEmail",
    "Normalizer",
    "StructuralAnalysis",
    "StructuralAnalyzer",
]
