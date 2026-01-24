"""Pipeline components for email body extraction."""

from yomail.pipeline.assembler import AssembledBody, BodyAssembler
from yomail.pipeline.confidence import ConfidenceGate, ConfidenceResult
from yomail.pipeline.crf import (
    LABELS,
    CRFSequenceLabeler,
    CRFTrainer,
    Label,
    LabeledLine,
    SequenceLabelingResult,
)
from yomail.pipeline.features import ExtractedFeatures, FeatureExtractor, LineFeatures
from yomail.pipeline.normalizer import NormalizedEmail, Normalizer
from yomail.pipeline.structural import AnnotatedLine, StructuralAnalysis, StructuralAnalyzer

__all__ = [
    "AnnotatedLine",
    "AssembledBody",
    "BodyAssembler",
    "ConfidenceGate",
    "ConfidenceResult",
    "CRFSequenceLabeler",
    "CRFTrainer",
    "ExtractedFeatures",
    "FeatureExtractor",
    "Label",
    "LabeledLine",
    "LABELS",
    "LineFeatures",
    "NormalizedEmail",
    "Normalizer",
    "SequenceLabelingResult",
    "StructuralAnalysis",
    "StructuralAnalyzer",
]
