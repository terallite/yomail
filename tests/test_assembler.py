"""Tests for the Body Assembler component."""

from yomail.pipeline.assembler import BodyAssembler
from yomail.pipeline.crf import Label, LabeledLine, SequenceLabelingResult


def _make_labeled_line(
    text: str,
    label: Label,
    confidence: float = 0.9,
) -> LabeledLine:
    """Create a LabeledLine with default probabilities."""
    # Simple probability distribution - label gets the confidence, others get the rest
    other_prob = (1.0 - confidence) / 6.0
    probs: dict[Label, float] = {
        "GREETING": other_prob,
        "BODY": other_prob,
        "CLOSING": other_prob,
        "SIGNATURE": other_prob,
        "QUOTE": other_prob,
        "SEPARATOR": other_prob,
        "OTHER": other_prob,
    }
    probs[label] = confidence

    return LabeledLine(
        text=text,
        label=label,
        confidence=confidence,
        label_probabilities=probs,
    )


def _make_result(lines: list[tuple[str, Label]]) -> SequenceLabelingResult:
    """Create a SequenceLabelingResult from (text, label) pairs."""
    labeled = tuple(_make_labeled_line(text, label) for text, label in lines)
    return SequenceLabelingResult(
        labeled_lines=labeled,
        sequence_probability=0.9,
    )


class TestSignatureBoundary:
    """Tests for signature boundary detection."""

    def test_no_signature(self) -> None:
        """No signature means all content considered."""
        result = _make_result([
            ("Hello", "BODY"),
            ("World", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.signature_index is None
        assert assembled.body_text == "Hello\nWorld"

    def test_signature_at_end(self) -> None:
        """Signature at end excludes signature lines."""
        result = _make_result([
            ("Hello", "BODY"),
            ("---", "SEPARATOR"),
            ("John Doe", "SIGNATURE"),
            ("john@example.com", "SIGNATURE"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.signature_index == 2
        assert "John Doe" not in assembled.body_text
        assert "Hello" in assembled.body_text

    def test_signature_excludes_all_after(self) -> None:
        """Everything after first SIGNATURE is excluded."""
        result = _make_result([
            ("Body line", "BODY"),
            ("Sig start", "SIGNATURE"),
            ("More body", "BODY"),  # This should be excluded
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.signature_index == 1
        assert "More body" not in assembled.body_text


class TestInlineQuotes:
    """Tests for inline vs trailing quote classification."""

    def test_inline_quote_included(self) -> None:
        """Quotes between BODY lines are inline and included."""
        result = _make_result([
            ("Before quote", "BODY"),
            ("> Quoted text", "QUOTE"),
            ("After quote", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert "> Quoted text" in assembled.body_text
        assert assembled.inline_quote_count == 1

    def test_trailing_quote_excluded(self) -> None:
        """Quotes at end (no BODY after) are excluded."""
        result = _make_result([
            ("Body text", "BODY"),
            ("> Old message", "QUOTE"),
            ("> More old", "QUOTE"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert "Body text" in assembled.body_text
        assert "Old message" not in assembled.body_text

    def test_leading_quote_excluded(self) -> None:
        """Quotes at start (no BODY before) are excluded."""
        result = _make_result([
            ("> Previous email", "QUOTE"),
            ("My reply", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert "Previous email" not in assembled.body_text
        assert "My reply" in assembled.body_text


class TestContentBlocks:
    """Tests for content block building."""

    def test_body_lines_accumulate(self) -> None:
        """Consecutive BODY lines form one block."""
        result = _make_result([
            ("Line 1", "BODY"),
            ("Line 2", "BODY"),
            ("Line 3", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == "Line 1\nLine 2\nLine 3"

    def test_separator_included_if_followed_by_body(self) -> None:
        """Separators are included when followed by more BODY."""
        result = _make_result([
            ("Paragraph 1", "BODY"),
            ("", "SEPARATOR"),
            ("Paragraph 2", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == "Paragraph 1\n\nParagraph 2"

    def test_trailing_separator_excluded(self) -> None:
        """Separators at end are not included."""
        result = _make_result([
            ("Content", "BODY"),
            ("", "SEPARATOR"),
            ("", "SEPARATOR"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == "Content"

    def test_greeting_included_when_adjacent_to_body(self) -> None:
        """GREETING lines are included in the block."""
        result = _make_result([
            ("Dear Sir", "GREETING"),
            ("Please find attached", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert "Dear Sir" in assembled.body_text

    def test_closing_included_when_adjacent_to_body(self) -> None:
        """CLOSING lines are included in the block."""
        result = _make_result([
            ("The attachment is ready", "BODY"),
            ("Best regards", "CLOSING"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert "Best regards" in assembled.body_text

    def test_other_creates_hard_break(self) -> None:
        """OTHER lines create hard breaks between blocks."""
        result = _make_result([
            ("Block 1 line 1", "BODY"),
            ("Block 1 line 2", "BODY"),
            ("Header noise", "OTHER"),
            ("Block 2 line 1", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        # Without signature, longest block is selected
        # Both blocks have 2 lines, first wins
        assert "Block 1 line 1" in assembled.body_text
        assert "Header noise" not in assembled.body_text


class TestBodySelection:
    """Tests for final body selection logic."""

    def test_with_signature_concatenates_all_blocks(self) -> None:
        """With signature, all blocks before signature are concatenated."""
        result = _make_result([
            ("Block 1", "BODY"),
            ("Noise", "OTHER"),
            ("Block 2", "BODY"),
            ("---", "SIGNATURE"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        # Both blocks should be in output
        assert "Block 1" in assembled.body_text
        assert "Block 2" in assembled.body_text

    def test_without_signature_selects_longest_block(self) -> None:
        """Without signature, longest block is selected."""
        result = _make_result([
            ("Short", "BODY"),
            ("Noise", "OTHER"),
            ("Longer line 1", "BODY"),
            ("Longer line 2", "BODY"),
            ("Longer line 3", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert "Longer line 1" in assembled.body_text
        assert "Short" not in assembled.body_text

    def test_equal_length_blocks_first_wins(self) -> None:
        """When blocks have equal length, first one is selected."""
        result = _make_result([
            ("First block", "BODY"),
            ("Noise", "OTHER"),
            ("Second block", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert "First block" in assembled.body_text
        assert "Second block" not in assembled.body_text


class TestEmptyInput:
    """Tests for edge cases with empty or minimal input."""

    def test_empty_result(self) -> None:
        """Empty input returns empty body."""
        result = SequenceLabelingResult(
            labeled_lines=(),
            sequence_probability=1.0,
        )
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == ""
        assert assembled.success is False
        assert assembled.body_lines == ()

    def test_only_signature(self) -> None:
        """Only signature lines means no body."""
        result = _make_result([
            ("John Doe", "SIGNATURE"),
            ("john@example.com", "SIGNATURE"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == ""
        assert assembled.success is False

    def test_only_quotes(self) -> None:
        """Only quotes (no body) means no body extracted."""
        result = _make_result([
            ("> Old message", "QUOTE"),
            ("> More old", "QUOTE"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == ""
        assert assembled.success is False
