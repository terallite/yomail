"""Tests for the StructuralAnalyzer component."""

from yomail import Normalizer, StructuralAnalyzer
from yomail.pipeline.content_filter import ContentFilter
from yomail.pipeline.structural import StructuralAnalysis


def _analyze(text: str) -> StructuralAnalysis:
    """Helper to run the full analysis pipeline."""
    normalizer = Normalizer()
    content_filter = ContentFilter()
    analyzer = StructuralAnalyzer()

    normalized = normalizer.normalize(text)
    filtered = content_filter.filter(normalized)
    return analyzer.analyze(filtered)


class TestQuoteDepth:
    """Quote depth detection tests."""

    def test_no_quotes(self) -> None:
        """Lines without quote markers have depth 0."""
        result = _analyze("Hello\nWorld")

        assert result.lines[0].quote_depth == 0
        assert result.lines[1].quote_depth == 0
        assert result.has_quotes is False

    def test_single_quote_marker(self) -> None:
        """Single > marker gives depth 1."""
        result = _analyze("> Quoted text")

        assert result.lines[0].quote_depth == 1
        assert result.has_quotes is True

    def test_nested_quotes(self) -> None:
        """Multiple > markers give corresponding depth."""
        result = _analyze(">> Nested quote\n>>> Triple nested")

        assert result.lines[0].quote_depth == 2
        assert result.lines[1].quote_depth == 3

    def test_quote_with_space(self) -> None:
        """Quote markers with spaces between them."""
        result = _analyze("> > Spaced quotes")

        assert result.lines[0].quote_depth == 2

    def test_pipe_quote_marker(self) -> None:
        """Pipe | is also a quote marker."""
        result = _analyze("| Pipe quoted")

        assert result.lines[0].quote_depth == 1

    def test_mixed_quote_markers(self) -> None:
        """Mixed > and | markers."""
        result = _analyze(">| Mixed markers")

        assert result.lines[0].quote_depth == 2

    def test_fullwidth_quote_normalized(self) -> None:
        """Full-width ＞ is normalized to > before analysis."""
        # Full-width ＞ should be normalized to half-width >
        result = _analyze("＞ Full-width quote")

        assert result.lines[0].quote_depth == 1

    def test_quote_indices(self) -> None:
        """First and last quote indices are tracked."""
        result = _analyze("Normal\n> Quoted\nNormal\n> Also quoted\nNormal")

        assert result.first_quote_index == 1
        assert result.last_quote_index == 3


class TestDelimiterDetection:
    """Delimiter line detection tests."""

    def test_hyphen_delimiter(self) -> None:
        """Hyphen delimiter line is detected."""
        result = _analyze("Before\n---\nAfter")

        assert result.lines[1].is_delimiter is True
        assert result.lines[2].preceded_by_delimiter is True

    def test_equals_delimiter(self) -> None:
        """Equals delimiter line is detected."""
        result = _analyze("Before\n===\nAfter")

        assert result.lines[1].is_delimiter is True

    def test_underscore_delimiter(self) -> None:
        """Underscore delimiter line is detected."""
        result = _analyze("Before\n___\nAfter")

        assert result.lines[1].is_delimiter is True

    def test_long_delimiter(self) -> None:
        """Long delimiter line is detected."""
        result = _analyze("Before\n" + "-" * 50 + "\nAfter")

        assert result.lines[1].is_delimiter is True

    def test_short_text_not_delimiter(self) -> None:
        """Short sequences of delimiter chars are not delimiters."""
        result = _analyze("a--b")

        assert result.lines[0].is_delimiter is False

    def test_blank_line_not_delimiter(self) -> None:
        """Blank lines are filtered out, so only content lines remain."""
        # With ContentFilter, blank lines are removed before analysis
        # This test verifies neither content line is marked as delimiter
        result = _analyze("Before\n\nAfter")

        # Only 2 content lines after filtering
        assert len(result.lines) == 2
        assert result.lines[0].is_delimiter is False
        assert result.lines[1].is_delimiter is False


class TestForwardReplyHeaders:
    """Forward/reply header detection tests."""

    def test_original_message_header(self) -> None:
        """-----Original Message----- is detected."""
        result = _analyze("Reply\n-----Original Message-----\n> Old")

        assert result.lines[1].is_forward_reply_header is True
        assert result.has_forward_reply is True

    def test_forwarded_message_header(self) -> None:
        """---------- Forwarded message --------- is detected."""
        result = _analyze("FYI\n---------- Forwarded message ----------")

        assert result.lines[1].is_forward_reply_header is True

    def test_on_date_wrote_header(self) -> None:
        """On [date] [person] wrote: is detected."""
        result = _analyze("On 2024/01/15, John Smith wrote:")

        assert result.lines[0].is_forward_reply_header is True

    def test_japanese_date_header(self) -> None:
        """Japanese date format attribution is detected."""
        result = _analyze("2024年1月15日 田中太郎:")

        assert result.lines[0].is_forward_reply_header is True

    def test_japanese_san_wrote_header(self) -> None:
        """Japanese さんからのメール pattern is detected."""
        result = _analyze("田中さんからのメール:")

        assert result.lines[0].is_forward_reply_header is True

    def test_normal_text_not_header(self) -> None:
        """Normal text is not mistaken for forward/reply header."""
        result = _analyze("お世話になっております。")

        assert result.lines[0].is_forward_reply_header is False
        assert result.has_forward_reply is False


class TestAnnotatedLineDataclass:
    """Tests for AnnotatedLine structure."""

    def test_line_index_tracking(self) -> None:
        """Line indices are correctly assigned."""
        result = _analyze("Line0\nLine1\nLine2")

        assert result.lines[0].line_index == 0
        assert result.lines[1].line_index == 1
        assert result.lines[2].line_index == 2

    def test_text_preserved(self) -> None:
        """Original text is preserved in annotations."""
        result = _analyze("Hello World")

        assert result.lines[0].text == "Hello World"

    def test_immutable(self) -> None:
        """AnnotatedLine is immutable."""
        result = _analyze("Test")

        try:
            result.lines[0].quote_depth = 5  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except AttributeError:
            pass  # Expected


class TestIntegration:
    """Integration tests with realistic email patterns."""

    def test_reply_email_structure(self) -> None:
        """Typical reply email with quoted content."""
        # Note: blank lines are filtered out, so we only check content lines
        text = """お世話になっております。

ご連絡ありがとうございます。

On 2024/01/15, Tanaka wrote:
> 先日の件について確認させてください。
> よろしくお願いします。

承知しました。"""

        result = _analyze(text)

        assert result.has_quotes is True
        assert result.has_forward_reply is True
        # The "On ... wrote:" line should be detected
        assert any(line.is_forward_reply_header for line in result.lines)
        # Quoted lines should have depth 1
        quoted_lines = [line for line in result.lines if line.quote_depth > 0]
        assert len(quoted_lines) == 2

    def test_email_with_signature_delimiter(self) -> None:
        """Email with signature after delimiter."""
        # Note: blank lines are filtered out, so we only check content lines
        text = """本文です。

よろしくお願いします。

---
山田太郎
ABC株式会社"""

        result = _analyze(text)

        # The --- line should be a delimiter
        delimiter_line = next(
            (line for line in result.lines if line.is_delimiter), None
        )
        assert delimiter_line is not None

        # Lines after delimiter should have preceded_by_delimiter for the first one
        delimiter_idx = delimiter_line.line_index
        if delimiter_idx + 1 < len(result.lines):
            assert result.lines[delimiter_idx + 1].preceded_by_delimiter is True
