"""Tests for ContentFilter component."""

from yomail.pipeline.content_filter import ContentFilter, ContentLine
from yomail.pipeline.normalizer import NormalizedEmail


def _make_normalized(text: str) -> NormalizedEmail:
    """Create NormalizedEmail from text."""
    lines = tuple(text.split("\n"))
    return NormalizedEmail(lines=lines, text=text)


class TestContentFilter:
    """Tests for content line filtering."""

    def test_all_content_no_blanks(self) -> None:
        """All content lines, no blanks."""
        normalized = _make_normalized("Line 1\nLine 2\nLine 3")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert len(result.content_lines) == 3
        assert result.whitespace_map.blank_positions == frozenset()
        assert result.whitespace_map.content_to_original == (0, 1, 2)

    def test_blank_in_middle(self) -> None:
        """Blank line between content lines."""
        normalized = _make_normalized("Line 1\n\nLine 2")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert len(result.content_lines) == 2
        assert result.whitespace_map.blank_positions == frozenset({1})
        assert result.content_lines[0].text == "Line 1"
        assert result.content_lines[1].text == "Line 2"

    def test_blank_lines_before_count(self) -> None:
        """blank_lines_before counts preceding blanks."""
        normalized = _make_normalized("Line 1\n\n\nLine 2")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert result.content_lines[0].blank_lines_before == 0
        assert result.content_lines[1].blank_lines_before == 2

    def test_blank_lines_after_count(self) -> None:
        """blank_lines_after counts following blanks."""
        normalized = _make_normalized("Line 1\n\n\nLine 2")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert result.content_lines[0].blank_lines_after == 2
        assert result.content_lines[1].blank_lines_after == 0

    def test_leading_blanks(self) -> None:
        """Blank lines at start of document."""
        normalized = _make_normalized("\n\nContent")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert len(result.content_lines) == 1
        assert result.content_lines[0].blank_lines_before == 2
        assert result.content_lines[0].text == "Content"

    def test_trailing_blanks(self) -> None:
        """Blank lines at end of document."""
        normalized = _make_normalized("Content\n\n")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert len(result.content_lines) == 1
        assert result.content_lines[0].blank_lines_after == 2

    def test_whitespace_only_is_blank(self) -> None:
        """Whitespace-only lines are treated as blank."""
        normalized = _make_normalized("Line 1\n   \nLine 2")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert len(result.content_lines) == 2
        assert result.whitespace_map.blank_positions == frozenset({1})

    def test_original_index_preserved(self) -> None:
        """original_index matches position in original document."""
        normalized = _make_normalized("A\n\nB\n\n\nC")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert result.content_lines[0].original_index == 0
        assert result.content_lines[1].original_index == 2
        assert result.content_lines[2].original_index == 5

    def test_content_to_original_mapping(self) -> None:
        """content_to_original correctly maps indices."""
        normalized = _make_normalized("A\n\nB\nC\n\nD")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        # Content indices 0,1,2,3 -> Original indices 0,2,3,5
        assert result.whitespace_map.content_to_original == (0, 2, 3, 5)

    def test_original_lines_preserved(self) -> None:
        """original_lines stores all original text."""
        text = "Line 1\n\nLine 2"
        normalized = _make_normalized(text)
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert result.original_lines == ("Line 1", "", "Line 2")

    def test_all_blanks(self) -> None:
        """Document with only blank lines."""
        normalized = _make_normalized("\n\n")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert len(result.content_lines) == 0
        assert result.whitespace_map.blank_positions == frozenset({0, 1, 2})

    def test_single_content_line(self) -> None:
        """Single content line, no blanks."""
        normalized = _make_normalized("Hello")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert len(result.content_lines) == 1
        assert result.content_lines[0].blank_lines_before == 0
        assert result.content_lines[0].blank_lines_after == 0


class TestWhitespaceMap:
    """Tests for WhitespaceMap structure."""

    def test_original_line_count(self) -> None:
        """original_line_count matches input."""
        normalized = _make_normalized("A\n\nB\nC")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert result.whitespace_map.original_line_count == 4

    def test_blank_positions_frozenset(self) -> None:
        """blank_positions is a frozenset."""
        normalized = _make_normalized("A\n\nB")
        filter_ = ContentFilter()
        result = filter_.filter(normalized)

        assert isinstance(result.whitespace_map.blank_positions, frozenset)


class TestContentLine:
    """Tests for ContentLine structure."""

    def test_dataclass_frozen(self) -> None:
        """ContentLine is immutable."""
        line = ContentLine(
            text="Test",
            original_index=0,
            blank_lines_before=1,
            blank_lines_after=2,
        )
        try:
            line.text = "Changed"  # type: ignore[misc]
            assert False, "Should not allow mutation"
        except AttributeError:
            pass  # Expected
