"""Confidence Gate for extraction quality assessment.

Computes confidence scores and applies thresholds to determine
whether an extraction result should be accepted or rejected.
"""

import logging
from dataclasses import dataclass

from yomail.pipeline.assembler import AssembledBody
from yomail.pipeline.crf import LabeledLine, SequenceLabelingResult

logger = logging.getLogger(__name__)

# Default thresholds
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_AMBIGUITY_THRESHOLD = 0.7
DEFAULT_AMBIGUITY_PENALTY = 0.2


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    """Result of confidence computation.

    Attributes:
        confidence: Final confidence score (0.0 to 1.0).
        base_confidence: Minimum marginal probability among body lines.
        ambiguity_penalty: Penalty applied for ambiguous extractions.
        passes_threshold: Whether confidence meets the threshold.
        threshold: The threshold that was applied.
        excluded_body_count: Number of excluded high-confidence BODY lines.
    """

    confidence: float
    base_confidence: float
    ambiguity_penalty: float
    passes_threshold: bool
    threshold: float
    excluded_body_count: int


class ConfidenceGate:
    """Computes and validates extraction confidence.

    Confidence computation (per DESIGN.md section 3.6):
    - Base confidence: minimum marginal probability among body-labeled lines
    - Ambiguity penalty: if high-confidence BODY labels exist outside the
      selected body region, reduce confidence

    Thresholds:
    - Confidence < threshold → extraction should be rejected
    - Configurable via constructor parameters
    """

    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        ambiguity_threshold: float = DEFAULT_AMBIGUITY_THRESHOLD,
        ambiguity_penalty: float = DEFAULT_AMBIGUITY_PENALTY,
    ) -> None:
        """Initialize the confidence gate.

        Args:
            confidence_threshold: Minimum confidence to accept extraction.
            ambiguity_threshold: Confidence level above which excluded BODY
                lines trigger an ambiguity penalty.
            ambiguity_penalty: Penalty to apply for each high-confidence
                excluded BODY line (capped at total penalty of 0.5).
        """
        self._confidence_threshold = confidence_threshold
        self._ambiguity_threshold = ambiguity_threshold
        self._ambiguity_penalty = ambiguity_penalty

    @property
    def confidence_threshold(self) -> float:
        """Get the confidence threshold."""
        return self._confidence_threshold

    def compute(
        self,
        labeling_result: SequenceLabelingResult,
        assembled: AssembledBody,
    ) -> ConfidenceResult:
        """Compute confidence for an extraction.

        Args:
            labeling_result: CRF labeling output.
            assembled: Body assembly output.

        Returns:
            ConfidenceResult with computed scores and threshold check.
        """
        labeled_lines = labeling_result.labeled_lines
        body_indices = set(assembled.body_lines)

        # Base confidence: minimum marginal probability among selected body lines
        base_confidence = self._compute_base_confidence(labeled_lines, body_indices)

        # Ambiguity penalty: high-confidence BODY labels outside selected region
        excluded_body_count, penalty = self._compute_ambiguity_penalty(
            labeled_lines, body_indices
        )

        # Final confidence
        confidence = max(0.0, base_confidence - penalty)

        return ConfidenceResult(
            confidence=confidence,
            base_confidence=base_confidence,
            ambiguity_penalty=penalty,
            passes_threshold=confidence >= self._confidence_threshold,
            threshold=self._confidence_threshold,
            excluded_body_count=excluded_body_count,
        )

    def _compute_base_confidence(
        self,
        labeled_lines: tuple[LabeledLine, ...],
        body_indices: set[int],
    ) -> float:
        """Compute base confidence as minimum marginal probability of body lines.

        The "weakest link" approach - confidence is limited by the least
        confident body line.

        Args:
            labeled_lines: All labeled lines.
            body_indices: Indices of lines selected for body.

        Returns:
            Minimum confidence among body lines, or 0.0 if no body lines.
        """
        if not body_indices:
            return 0.0

        min_confidence = 1.0
        for idx in body_indices:
            line = labeled_lines[idx]
            # Use the confidence of the line's actual predicted label
            min_confidence = min(min_confidence, line.confidence)

        return min_confidence

    def _compute_ambiguity_penalty(
        self,
        labeled_lines: tuple[LabeledLine, ...],
        body_indices: set[int],
    ) -> tuple[int, float]:
        """Compute ambiguity penalty for high-confidence excluded BODY lines.

        If lines outside the selected body have high confidence of being BODY,
        this suggests the model is uncertain about which region is the "real" body.

        Args:
            labeled_lines: All labeled lines.
            body_indices: Indices of lines selected for body.

        Returns:
            Tuple of (count of excluded high-confidence BODY lines, penalty).
        """
        excluded_body_count = 0

        for idx, line in enumerate(labeled_lines):
            if idx in body_indices:
                continue

            # Check if this excluded line has high confidence as BODY
            body_prob = line.label_probabilities.get("BODY", 0.0)
            if body_prob >= self._ambiguity_threshold:
                excluded_body_count += 1

        # Apply penalty (capped at 0.5 total)
        penalty = min(0.5, excluded_body_count * self._ambiguity_penalty)

        return excluded_body_count, penalty
