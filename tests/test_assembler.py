"""Tests for the Body Assembler component."""

from typing import cast

from yomail.pipeline.assembler import BodyAssembler
from yomail.pipeline.crf import Label
from yomail.pipeline.reconstructor import ReconstructedDocument, ReconstructedLine


def _make_reconstructed_line(
    text: str,
    label: Label,
    original_index: int,
    is_blank: bool = False,
    confidence: float = 0.9,
) -> ReconstructedLine:
    """Create a ReconstructedLine with default values."""
    return ReconstructedLine(
        text=text,
        original_index=original_index,
        is_blank=is_blank,
        label=label,
        confidence=confidence if not is_blank else None,
        label_probabilities=None,
    )


def _make_doc(lines: list[tuple[str, Label]]) -> ReconstructedDocument:
    """Create a ReconstructedDocument from (text, label) pairs.

    All lines are treated as content (non-blank) lines.
    """
    reconstructed_lines: list[ReconstructedLine] = []
    for idx, line_tuple in enumerate(lines):
        text, label = line_tuple
        reconstructed_lines.append(_make_reconstructed_line(text, cast(Label, label), idx))
    return ReconstructedDocument(
        lines=tuple(reconstructed_lines),
        sequence_probability=0.9,
    )


class TestSignatureBoundary:
    """Tests for signature boundary detection."""

    def test_no_signature(self) -> None:
        """No signature means all content considered."""
        result = _make_doc([
            ("Hello", "BODY"),
            ("World", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.signature_index is None
        assert assembled.body_text == "Hello\nWorld"

    def test_signature_at_end(self) -> None:
        """Signature at end excludes signature lines."""
        result = _make_doc([
            ("Hello", "BODY"),
            ("---", "OTHER"),
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
        result = _make_doc([
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
        result = _make_doc([
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
        result = _make_doc([
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
        result = _make_doc([
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
        result = _make_doc([
            ("Line 1", "BODY"),
            ("Line 2", "BODY"),
            ("Line 3", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == "Line 1\nLine 2\nLine 3"

    def test_other_included_if_followed_by_body(self) -> None:
        """OTHER lines are included when between BODY lines."""
        result = _make_doc([
            ("Paragraph 1", "BODY"),
            ("[some header noise]", "OTHER"),
            ("Paragraph 2", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == "Paragraph 1\n[some header noise]\nParagraph 2"

    def test_trailing_other_excluded(self) -> None:
        """OTHER lines at end are not included."""
        result = _make_doc([
            ("Content", "BODY"),
            ("[noise 1]", "OTHER"),
            ("[noise 2]", "OTHER"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == "Content"

    def test_greeting_included_when_adjacent_to_body(self) -> None:
        """GREETING lines are included in the block."""
        result = _make_doc([
            ("Dear Sir", "GREETING"),
            ("Please find attached", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert "Dear Sir" in assembled.body_text

    def test_closing_included_when_adjacent_to_body(self) -> None:
        """CLOSING lines are included in the block."""
        result = _make_doc([
            ("The attachment is ready", "BODY"),
            ("Best regards", "CLOSING"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert "Best regards" in assembled.body_text

    def test_other_is_neutral(self) -> None:
        """OTHER lines are neutral and don't break blocks."""
        result = _make_doc([
            ("Block 1 line 1", "BODY"),
            ("Block 1 line 2", "BODY"),
            ("Blank line", "OTHER"),
            ("Block 2 line 1", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        # OTHER is neutral - all content flows into one block
        assert "Block 1 line 1" in assembled.body_text
        assert "Block 2 line 1" in assembled.body_text
        # OTHER between content is included (buffered like separator)
        assert "Blank line" in assembled.body_text


class TestBlankLineHandling:
    """Tests for blank line handling in body assembly."""

    def test_blank_lines_between_body_included(self) -> None:
        """Blank lines between body content are included in output."""
        lines = [
            _make_reconstructed_line("Para 1", "BODY", 0),
            _make_reconstructed_line("", "BODY", 1, is_blank=True),  # inherits BODY
            _make_reconstructed_line("Para 2", "BODY", 2),
        ]
        doc = ReconstructedDocument(lines=tuple(lines), sequence_probability=0.9)
        assembler = BodyAssembler()
        assembled = assembler.assemble(doc)

        # Blank line should be included in output
        assert assembled.body_text == "Para 1\n\nPara 2"
        assert assembled.body_lines == (0, 1, 2)

    def test_trailing_blank_lines_excluded(self) -> None:
        """Blank lines at the end of body are excluded."""
        lines = [
            _make_reconstructed_line("Content", "BODY", 0),
            _make_reconstructed_line("", "BODY", 1, is_blank=True),
            _make_reconstructed_line("", "BODY", 2, is_blank=True),
        ]
        doc = ReconstructedDocument(lines=tuple(lines), sequence_probability=0.9)
        assembler = BodyAssembler()
        assembled = assembler.assemble(doc)

        # Trailing blanks are not included (no content after them)
        assert assembled.body_text == "Content"
        assert assembled.body_lines == (0,)


class TestBodySelection:
    """Tests for final body selection logic."""

    def test_with_signature_concatenates_all_blocks(self) -> None:
        """With signature, all blocks before signature are concatenated."""
        result = _make_doc([
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
        """Without signature, longest block is selected (blocks split by leading quote)."""
        result = _make_doc([
            ("> leading quote", "QUOTE"),  # Leading quote - creates first empty block
            ("Body line 1", "BODY"),
            ("Body line 2", "BODY"),
            ("Body line 3", "BODY"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        # Body block is selected (leading quote excluded)
        assert "Body line 1" in assembled.body_text
        assert "leading quote" not in assembled.body_text

    def test_without_signature_all_content_in_one_block(self) -> None:
        """Without signature or quotes, all content flows into one block."""
        result = _make_doc([
            ("Greeting", "GREETING"),
            ("", "OTHER"),
            ("Body content", "BODY"),
            ("", "OTHER"),
            ("Closing", "CLOSING"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        # All content in one block
        assert "Greeting" in assembled.body_text
        assert "Body content" in assembled.body_text
        assert "Closing" in assembled.body_text


class TestEmptyInput:
    """Tests for edge cases with empty or minimal input."""

    def test_empty_result(self) -> None:
        """Empty input returns empty body."""
        doc = ReconstructedDocument(
            lines=(),
            sequence_probability=1.0,
        )
        assembler = BodyAssembler()
        assembled = assembler.assemble(doc)

        assert assembled.body_text == ""
        assert assembled.success is False
        assert assembled.body_lines == ()

    def test_only_signature(self) -> None:
        """Only signature lines means no body."""
        result = _make_doc([
            ("John Doe", "SIGNATURE"),
            ("john@example.com", "SIGNATURE"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == ""
        assert assembled.success is False

    def test_only_quotes(self) -> None:
        """Only quotes (no body) means no body extracted."""
        result = _make_doc([
            ("> Old message", "QUOTE"),
            ("> More old", "QUOTE"),
        ])
        assembler = BodyAssembler()
        assembled = assembler.assemble(result)

        assert assembled.body_text == ""
        assert assembled.success is False
