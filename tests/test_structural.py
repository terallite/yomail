"""Tests for the StructuralAnalyzer component."""

from yomail import Normalizer, StructuralAnalyzer


class TestQuoteDepth:
    """Quote depth detection tests."""

    def test_no_quotes(self) -> None:
        """Lines without quote markers have depth 0."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("Hello\nWorld")
        result = analyzer.analyze(normalized)

        assert result.lines[0].quote_depth == 0
        assert result.lines[1].quote_depth == 0
        assert result.has_quotes is False

    def test_single_quote_marker(self) -> None:
        """Single > marker gives depth 1."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("> Quoted text")
        result = analyzer.analyze(normalized)

        assert result.lines[0].quote_depth == 1
        assert result.has_quotes is True

    def test_nested_quotes(self) -> None:
        """Multiple > markers give corresponding depth."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize(">> Nested quote\n>>> Triple nested")
        result = analyzer.analyze(normalized)

        assert result.lines[0].quote_depth == 2
        assert result.lines[1].quote_depth == 3

    def test_quote_with_space(self) -> None:
        """Quote markers with spaces between them."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("> > Spaced quotes")
        result = analyzer.analyze(normalized)

        assert result.lines[0].quote_depth == 2

    def test_pipe_quote_marker(self) -> None:
        """Pipe | is also a quote marker."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("| Pipe quoted")
        result = analyzer.analyze(normalized)

        assert result.lines[0].quote_depth == 1

    def test_mixed_quote_markers(self) -> None:
        """Mixed > and | markers."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize(">| Mixed markers")
        result = analyzer.analyze(normalized)

        assert result.lines[0].quote_depth == 2

    def test_fullwidth_quote_normalized(self) -> None:
        """Full-width ＞ is normalized to > before analysis."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        # Full-width ＞ should be normalized to half-width >
        normalized = normalizer.normalize("＞ Full-width quote")
        result = analyzer.analyze(normalized)

        assert result.lines[0].quote_depth == 1

    def test_quote_indices(self) -> None:
        """First and last quote indices are tracked."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        text = "Normal\n> Quoted\nNormal\n> Also quoted\nNormal"
        normalized = normalizer.normalize(text)
        result = analyzer.analyze(normalized)

        assert result.first_quote_index == 1
        assert result.last_quote_index == 3


class TestDelimiterDetection:
    """Delimiter line detection tests."""

    def test_hyphen_delimiter(self) -> None:
        """Hyphen delimiter line is detected."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("Before\n---\nAfter")
        result = analyzer.analyze(normalized)

        assert result.lines[1].is_delimiter is True
        assert result.lines[2].preceded_by_delimiter is True

    def test_equals_delimiter(self) -> None:
        """Equals delimiter line is detected."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("Before\n===\nAfter")
        result = analyzer.analyze(normalized)

        assert result.lines[1].is_delimiter is True

    def test_underscore_delimiter(self) -> None:
        """Underscore delimiter line is detected."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("Before\n___\nAfter")
        result = analyzer.analyze(normalized)

        assert result.lines[1].is_delimiter is True

    def test_long_delimiter(self) -> None:
        """Long delimiter line is detected."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("Before\n" + "-" * 50 + "\nAfter")
        result = analyzer.analyze(normalized)

        assert result.lines[1].is_delimiter is True

    def test_short_text_not_delimiter(self) -> None:
        """Short sequences of delimiter chars are not delimiters."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("a--b")
        result = analyzer.analyze(normalized)

        assert result.lines[0].is_delimiter is False

    def test_blank_line_not_delimiter(self) -> None:
        """Blank lines are not delimiters."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("Before\n\nAfter")
        result = analyzer.analyze(normalized)

        assert result.lines[1].is_delimiter is False


class TestForwardReplyHeaders:
    """Forward/reply header detection tests."""

    def test_original_message_header(self) -> None:
        """-----Original Message----- is detected."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("Reply\n-----Original Message-----\n> Old")
        result = analyzer.analyze(normalized)

        assert result.lines[1].is_forward_reply_header is True
        assert result.has_forward_reply is True

    def test_forwarded_message_header(self) -> None:
        """---------- Forwarded message --------- is detected."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("FYI\n---------- Forwarded message ----------")
        result = analyzer.analyze(normalized)

        assert result.lines[1].is_forward_reply_header is True

    def test_on_date_wrote_header(self) -> None:
        """On [date] [person] wrote: is detected."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("On 2024/01/15, John Smith wrote:")
        result = analyzer.analyze(normalized)

        assert result.lines[0].is_forward_reply_header is True

    def test_japanese_date_header(self) -> None:
        """Japanese date format attribution is detected."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("2024年1月15日 田中太郎:")
        result = analyzer.analyze(normalized)

        assert result.lines[0].is_forward_reply_header is True

    def test_japanese_san_wrote_header(self) -> None:
        """Japanese さんからのメール pattern is detected."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("田中さんからのメール:")
        result = analyzer.analyze(normalized)

        assert result.lines[0].is_forward_reply_header is True

    def test_normal_text_not_header(self) -> None:
        """Normal text is not mistaken for forward/reply header."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("お世話になっております。")
        result = analyzer.analyze(normalized)

        assert result.lines[0].is_forward_reply_header is False
        assert result.has_forward_reply is False


class TestAnnotatedLineDataclass:
    """Tests for AnnotatedLine structure."""

    def test_line_index_tracking(self) -> None:
        """Line indices are correctly assigned."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("Line0\nLine1\nLine2")
        result = analyzer.analyze(normalized)

        assert result.lines[0].line_index == 0
        assert result.lines[1].line_index == 1
        assert result.lines[2].line_index == 2

    def test_text_preserved(self) -> None:
        """Original text is preserved in annotations."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("Hello World")
        result = analyzer.analyze(normalized)

        assert result.lines[0].text == "Hello World"

    def test_immutable(self) -> None:
        """AnnotatedLine is immutable."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        normalized = normalizer.normalize("Test")
        result = analyzer.analyze(normalized)

        try:
            result.lines[0].quote_depth = 5  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except AttributeError:
            pass  # Expected


class TestIntegration:
    """Integration tests with realistic email patterns."""

    def test_reply_email_structure(self) -> None:
        """Typical reply email with quoted content."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        text = """お世話になっております。

ご連絡ありがとうございます。

On 2024/01/15, Tanaka wrote:
> 先日の件について確認させてください。
> よろしくお願いします。

承知しました。"""

        normalized = normalizer.normalize(text)
        result = analyzer.analyze(normalized)

        assert result.has_quotes is True
        assert result.has_forward_reply is True
        # The "On ... wrote:" line should be detected
        assert any(line.is_forward_reply_header for line in result.lines)
        # Quoted lines should have depth 1
        quoted_lines = [line for line in result.lines if line.quote_depth > 0]
        assert len(quoted_lines) == 2

    def test_email_with_signature_delimiter(self) -> None:
        """Email with signature after delimiter."""
        normalizer = Normalizer()
        analyzer = StructuralAnalyzer()

        text = """本文です。

よろしくお願いします。

---
山田太郎
ABC株式会社"""

        normalized = normalizer.normalize(text)
        result = analyzer.analyze(normalized)

        # The --- line should be a delimiter
        delimiter_line = next(
            (line for line in result.lines if line.is_delimiter), None
        )
        assert delimiter_line is not None

        # Lines after delimiter should have preceded_by_delimiter for the first one
        delimiter_idx = delimiter_line.line_index
        if delimiter_idx + 1 < len(result.lines):
            assert result.lines[delimiter_idx + 1].preceded_by_delimiter is True
