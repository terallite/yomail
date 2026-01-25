"""Tests for the Confidence Gate component."""

from yomail.pipeline.assembler import AssembledBody
from yomail.pipeline.confidence import ConfidenceGate
from yomail.pipeline.crf import Label, LabeledLine, SequenceLabelingResult


def _make_labeled_line(
    text: str,
    label: Label,
    confidence: float = 0.9,
    body_prob: float | None = None,
) -> LabeledLine:
    """Create a LabeledLine with configurable probabilities."""
    probs: dict[Label, float] = {
        "GREETING": 0.0,
        "BODY": 0.0,
        "CLOSING": 0.0,
        "SIGNATURE": 0.0,
        "QUOTE": 0.0,
        "OTHER": 0.0,
    }
    probs[label] = confidence

    # Allow explicit body probability override for ambiguity testing
    if body_prob is not None:
        probs["BODY"] = body_prob

    return LabeledLine(
        text=text,
        label=label,
        confidence=confidence,
        label_probabilities=probs,
    )


class TestBaseConfidence:
    """Tests for base confidence computation."""

    def test_single_line_confidence(self) -> None:
        """Single line confidence is that line's confidence."""
        lines = (_make_labeled_line("Body", "BODY", confidence=0.85),)
        labeling = SequenceLabelingResult(labeled_lines=lines, sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="Body",
            body_lines=(0,),
            signature_index=None,
            inline_quote_count=0,
            success=True,
        )

        gate = ConfidenceGate()
        result = gate.compute(labeling, assembled)

        assert result.base_confidence == 0.85

    def test_p10_small_set_uses_minimum(self) -> None:
        """For <10 lines, P10 falls back to minimum (index 0)."""
        lines = (
            _make_labeled_line("Line 1", "BODY", confidence=0.95),
            _make_labeled_line("Line 2", "BODY", confidence=0.70),  # Weakest
            _make_labeled_line("Line 3", "BODY", confidence=0.85),
        )
        labeling = SequenceLabelingResult(labeled_lines=lines, sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="Line 1\nLine 2\nLine 3",
            body_lines=(0, 1, 2),
            signature_index=None,
            inline_quote_count=0,
            success=True,
        )

        gate = ConfidenceGate()
        result = gate.compute(labeling, assembled)

        # With 3 lines, P10 index = 3 // 10 = 0, so minimum is used
        assert result.base_confidence == 0.70

    def test_p10_ignores_single_weak_outlier(self) -> None:
        """For 10+ lines, P10 ignores the single weakest line."""
        # 10 lines: 9 high confidence, 1 weak outlier
        lines = tuple(
            _make_labeled_line(f"Line {i}", "BODY", confidence=0.90)
            for i in range(9)
        ) + (_make_labeled_line("Weak line", "BODY", confidence=0.40),)

        labeling = SequenceLabelingResult(labeled_lines=lines, sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="\n".join(f"Line {i}" for i in range(10)),
            body_lines=tuple(range(10)),
            signature_index=None,
            inline_quote_count=0,
            success=True,
        )

        gate = ConfidenceGate()
        result = gate.compute(labeling, assembled)

        # With 10 lines, P10 index = 10 // 10 = 1
        # Sorted confidences: [0.40, 0.90, 0.90, ...], so P10 = 0.90
        assert result.base_confidence == 0.90

    def test_empty_body_zero_confidence(self) -> None:
        """Empty body has zero confidence."""
        lines = (_make_labeled_line("Sig", "SIGNATURE", confidence=0.9),)
        labeling = SequenceLabelingResult(labeled_lines=lines, sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="",
            body_lines=(),
            signature_index=0,
            inline_quote_count=0,
            success=False,
        )

        gate = ConfidenceGate()
        result = gate.compute(labeling, assembled)

        assert result.base_confidence == 0.0


class TestAmbiguityPenalty:
    """Tests for ambiguity penalty computation."""

    def test_no_excluded_body_no_penalty(self) -> None:
        """No excluded high-confidence BODY lines means no penalty."""
        lines = (
            _make_labeled_line("Body", "BODY", confidence=0.9),
            _make_labeled_line("Sig", "SIGNATURE", confidence=0.9),
        )
        labeling = SequenceLabelingResult(labeled_lines=lines, sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="Body",
            body_lines=(0,),
            signature_index=1,
            inline_quote_count=0,
            success=True,
        )

        gate = ConfidenceGate()
        result = gate.compute(labeling, assembled)

        assert result.ambiguity_penalty == 0.0
        assert result.excluded_body_count == 0

    def test_excluded_high_confidence_body_penalized(self) -> None:
        """Excluded lines with high BODY probability trigger penalty."""
        lines = (
            _make_labeled_line("Selected body", "BODY", confidence=0.9),
            # This line is labeled QUOTE but has high BODY probability
            _make_labeled_line("Excluded line", "QUOTE", confidence=0.8, body_prob=0.75),
        )
        labeling = SequenceLabelingResult(labeled_lines=lines, sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="Selected body",
            body_lines=(0,),
            signature_index=None,
            inline_quote_count=0,
            success=True,
        )

        gate = ConfidenceGate()
        result = gate.compute(labeling, assembled)

        assert result.excluded_body_count == 1
        assert result.ambiguity_penalty > 0.0

    def test_penalty_capped_at_half(self) -> None:
        """Ambiguity penalty is capped at 0.5."""
        # Create many excluded lines with high BODY probability
        lines = [_make_labeled_line("Selected", "BODY", confidence=0.9)]
        for i in range(10):
            lines.append(
                _make_labeled_line(f"Excluded {i}", "QUOTE", confidence=0.8, body_prob=0.8)
            )

        labeling = SequenceLabelingResult(
            labeled_lines=tuple(lines), sequence_probability=0.9
        )
        assembled = AssembledBody(
            body_text="Selected",
            body_lines=(0,),
            signature_index=None,
            inline_quote_count=0,
            success=True,
        )

        gate = ConfidenceGate()
        result = gate.compute(labeling, assembled)

        assert result.ambiguity_penalty <= 0.5


class TestThresholdCheck:
    """Tests for threshold checking."""

    def test_above_threshold_passes(self) -> None:
        """Confidence above threshold passes."""
        lines = (_make_labeled_line("Body", "BODY", confidence=0.8),)
        labeling = SequenceLabelingResult(labeled_lines=lines, sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="Body",
            body_lines=(0,),
            signature_index=None,
            inline_quote_count=0,
            success=True,
        )

        gate = ConfidenceGate(confidence_threshold=0.5)
        result = gate.compute(labeling, assembled)

        assert result.passes_threshold is True
        assert result.threshold == 0.5

    def test_below_threshold_fails(self) -> None:
        """Confidence below threshold fails."""
        lines = (_make_labeled_line("Body", "BODY", confidence=0.4),)
        labeling = SequenceLabelingResult(labeled_lines=lines, sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="Body",
            body_lines=(0,),
            signature_index=None,
            inline_quote_count=0,
            success=True,
        )

        gate = ConfidenceGate(confidence_threshold=0.5)
        result = gate.compute(labeling, assembled)

        assert result.passes_threshold is False

    def test_custom_threshold(self) -> None:
        """Custom threshold is respected."""
        lines = (_make_labeled_line("Body", "BODY", confidence=0.6),)
        labeling = SequenceLabelingResult(labeled_lines=lines, sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="Body",
            body_lines=(0,),
            signature_index=None,
            inline_quote_count=0,
            success=True,
        )

        strict_gate = ConfidenceGate(confidence_threshold=0.7)
        lenient_gate = ConfidenceGate(confidence_threshold=0.5)

        strict_result = strict_gate.compute(labeling, assembled)
        lenient_result = lenient_gate.compute(labeling, assembled)

        assert strict_result.passes_threshold is False
        assert lenient_result.passes_threshold is True


class TestFinalConfidence:
    """Tests for final confidence computation."""

    def test_confidence_is_base_minus_penalty(self) -> None:
        """Final confidence is base minus penalty."""
        lines = (
            _make_labeled_line("Selected", "BODY", confidence=0.8),
            _make_labeled_line("Excluded", "QUOTE", confidence=0.8, body_prob=0.75),
        )
        labeling = SequenceLabelingResult(labeled_lines=tuple(lines), sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="Selected",
            body_lines=(0,),
            signature_index=None,
            inline_quote_count=0,
            success=True,
        )

        gate = ConfidenceGate(ambiguity_penalty=0.1)
        result = gate.compute(labeling, assembled)

        expected = 0.8 - 0.1  # base - penalty
        assert abs(result.confidence - expected) < 0.01

    def test_confidence_minimum_zero(self) -> None:
        """Confidence cannot go below zero."""
        lines = (
            _make_labeled_line("Selected", "BODY", confidence=0.3),
            _make_labeled_line("Excluded", "QUOTE", confidence=0.8, body_prob=0.8),
            _make_labeled_line("Excluded 2", "QUOTE", confidence=0.8, body_prob=0.8),
            _make_labeled_line("Excluded 3", "QUOTE", confidence=0.8, body_prob=0.8),
        )
        labeling = SequenceLabelingResult(labeled_lines=tuple(lines), sequence_probability=0.9)
        assembled = AssembledBody(
            body_text="Selected",
            body_lines=(0,),
            signature_index=None,
            inline_quote_count=0,
            success=True,
        )

        gate = ConfidenceGate(ambiguity_penalty=0.2)
        result = gate.compute(labeling, assembled)

        assert result.confidence >= 0.0
