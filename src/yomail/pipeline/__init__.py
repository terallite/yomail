"""Pipeline components for email body extraction."""

from yomail.pipeline.features import ExtractedFeatures, FeatureExtractor, LineFeatures
from yomail.pipeline.normalizer import NormalizedEmail, Normalizer
from yomail.pipeline.structural import AnnotatedLine, StructuralAnalysis, StructuralAnalyzer

__all__ = [
    "AnnotatedLine",
    "ExtractedFeatures",
    "FeatureExtractor",
    "LineFeatures",
    "NormalizedEmail",
    "Normalizer",
    "StructuralAnalysis",
    "StructuralAnalyzer",
]
