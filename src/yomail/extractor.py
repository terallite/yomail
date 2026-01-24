"""EmailBodyExtractor - Main public interface for body extraction.

Provides three extraction methods:
- extract(): Strict extraction, raises on failure
- extract_safe(): Safe extraction, returns None on failure
- extract_with_metadata(): Full result with debugging info
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from yomail.exceptions import (
    ExtractionError,
    InvalidInputError,
    LowConfidenceError,
    NoBodyDetectedError,
)
from yomail.pipeline.assembler import BodyAssembler
from yomail.pipeline.confidence import ConfidenceGate
from yomail.pipeline.crf import CRFSequenceLabeler, LabeledLine
from yomail.pipeline.features import FeatureExtractor
from yomail.pipeline.normalizer import Normalizer
from yomail.pipeline.structural import StructuralAnalyzer

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Full extraction result with metadata.

    Attributes:
        body: Extracted body text, or None if extraction failed.
        confidence: Confidence score (0.0 to 1.0).
        success: Whether extraction succeeded.
        error: Error if extraction failed, None otherwise.
        labeled_lines: All lines with their labels (for debugging).
        signature_detected: Whether a signature was found.
        inline_quotes_included: Number of inline quote lines in body.
    """

    body: str | None
    confidence: float
    success: bool
    error: ExtractionError | None
    labeled_lines: tuple[LabeledLine, ...]
    signature_detected: bool
    inline_quotes_included: int


class EmailBodyExtractor:
    """Main class for extracting body text from Japanese emails.

    The extraction pipeline:
    1. Normalize text (encoding, Unicode, headers)
    2. Analyze structure (quotes, delimiters)
    3. Extract features for CRF
    4. Label lines with CRF model
    5. Assemble body from labeled lines
    6. Validate confidence

    Example:
        extractor = EmailBodyExtractor()

        # Strict extraction (raises on failure)
        body = extractor.extract(email_text)

        # Safe extraction (returns None on failure)
        body = extractor.extract_safe(email_text)

        # Full metadata
        result = extractor.extract_with_metadata(email_text)
    """

    def __init__(
        self,
        model_path: Path | str | None = None,
        confidence_threshold: float = 0.5,
    ) -> None:
        """Initialize the extractor.

        Args:
            model_path: Path to trained CRF model. Required for extraction.
            confidence_threshold: Minimum confidence to accept extraction.
        """
        # Pipeline components
        self._normalizer = Normalizer()
        self._structural_analyzer = StructuralAnalyzer()
        self._feature_extractor = FeatureExtractor()
        self._crf_labeler = CRFSequenceLabeler(model_path)
        self._body_assembler = BodyAssembler()
        self._confidence_gate = ConfidenceGate(confidence_threshold=confidence_threshold)

        self._model_path = Path(model_path) if model_path else None

    def load_model(self, model_path: Path | str) -> None:
        """Load a CRF model.

        Args:
            model_path: Path to the model file.
        """
        self._crf_labeler.load_model(model_path)
        self._model_path = Path(model_path)

    @property
    def is_model_loaded(self) -> bool:
        """Whether a model is currently loaded."""
        return self._crf_labeler.is_loaded

    def extract(self, email_text: str) -> str:
        """Extract body text from an email.

        Args:
            email_text: Raw email text (headers optional, body required).

        Returns:
            Extracted body text.

        Raises:
            InvalidInputError: If input is empty or invalid.
            NoBodyDetectedError: If no body content found.
            LowConfidenceError: If confidence is below threshold.
            RuntimeError: If no model is loaded.
        """
        result = self.extract_with_metadata(email_text)

        if result.error is not None:
            raise result.error

        if result.body is None:
            raise NoBodyDetectedError(message="No body content extracted")

        return result.body

    def extract_safe(self, email_text: str) -> str | None:
        """Extract body text, returning None on any failure.

        Args:
            email_text: Raw email text.

        Returns:
            Extracted body text, or None if extraction failed.
        """
        try:
            result = self.extract_with_metadata(email_text)
            return result.body if result.success else None
        except Exception:
            logger.exception("Unexpected error during extraction")
            return None

    def extract_with_metadata(self, email_text: str) -> ExtractionResult:
        """Extract body with full metadata.

        Args:
            email_text: Raw email text.

        Returns:
            ExtractionResult with body, confidence, and debugging info.
        """
        # Input validation
        if not email_text or not email_text.strip():
            return ExtractionResult(
                body=None,
                confidence=0.0,
                success=False,
                error=InvalidInputError(message="Empty input"),
                labeled_lines=(),
                signature_detected=False,
                inline_quotes_included=0,
            )

        try:
            # Step 1: Normalize
            normalized = self._normalizer.normalize(email_text)

            if not normalized.lines:
                return ExtractionResult(
                    body=None,
                    confidence=0.0,
                    success=False,
                    error=InvalidInputError(message="Empty after normalization"),
                    labeled_lines=(),
                    signature_detected=False,
                    inline_quotes_included=0,
                )

            # Step 2: Structural analysis
            structural = self._structural_analyzer.analyze(normalized)

            # Step 3: Feature extraction
            features = self._feature_extractor.extract(structural)

            # Step 4: CRF labeling
            labeling = self._crf_labeler.predict(features, normalized.lines)

            # Step 5: Body assembly
            assembled = self._body_assembler.assemble(labeling)

            # Step 6: Confidence check
            confidence_result = self._confidence_gate.compute(labeling, assembled)

            # Determine success and error
            error: ExtractionError | None = None
            success = True

            if not assembled.success:
                error = NoBodyDetectedError(message="No body content found")
                success = False
            elif not confidence_result.passes_threshold:
                error = LowConfidenceError(
                    message="Extraction confidence below threshold",
                    confidence=confidence_result.confidence,
                    threshold=confidence_result.threshold,
                )
                success = False

            return ExtractionResult(
                body=assembled.body_text if assembled.success else None,
                confidence=confidence_result.confidence,
                success=success,
                error=error,
                labeled_lines=labeling.labeled_lines,
                signature_detected=assembled.signature_index is not None,
                inline_quotes_included=assembled.inline_quote_count,
            )

        except InvalidInputError as exc:
            return ExtractionResult(
                body=None,
                confidence=0.0,
                success=False,
                error=exc,
                labeled_lines=(),
                signature_detected=False,
                inline_quotes_included=0,
            )
        except RuntimeError as exc:
            # Model not loaded
            logger.error("Extraction failed: %s", exc)
            return ExtractionResult(
                body=None,
                confidence=0.0,
                success=False,
                error=InvalidInputError(message=str(exc)),
                labeled_lines=(),
                signature_detected=False,
                inline_quotes_included=0,
            )
