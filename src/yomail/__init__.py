"""yomail - Extract body text from Japanese business emails."""

from yomail.exceptions import (
    ExtractionError,
    InvalidInputError,
    LowConfidenceError,
    NoBodyDetectedError,
)
from yomail.pipeline import (
    AnnotatedLine,
    AssembledBody,
    BodyAssembler,
    ConfidenceGate,
    ConfidenceResult,
    CRFSequenceLabeler,
    CRFTrainer,
    ExtractedFeatures,
    FeatureExtractor,
    Label,
    LabeledLine,
    LABELS,
    LineFeatures,
    NormalizedEmail,
    Normalizer,
    SequenceLabelingResult,
    StructuralAnalysis,
    StructuralAnalyzer,
)

__version__ = "0.1.0"

__all__ = [
    "AnnotatedLine",
    "AssembledBody",
    "BodyAssembler",
    "ConfidenceGate",
    "ConfidenceResult",
    "CRFSequenceLabeler",
    "CRFTrainer",
    "ExtractionError",
    "ExtractedFeatures",
    "FeatureExtractor",
    "InvalidInputError",
    "Label",
    "LabeledLine",
    "LABELS",
    "LineFeatures",
    "LowConfidenceError",
    "NoBodyDetectedError",
    "NormalizedEmail",
    "Normalizer",
    "SequenceLabelingResult",
    "StructuralAnalysis",
    "StructuralAnalyzer",
]
