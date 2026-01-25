"""Tests for Reconstructor component."""

from yomail.pipeline.content_filter import ContentFilter, WhitespaceMap
from yomail.pipeline.crf import Label, LabeledLine, SequenceLabelingResult
from yomail.pipeline.normalizer import NormalizedEmail
from yomail.pipeline.reconstructor import ReconstructedLine, Reconstructor


def _make_normalized(text: str) -> NormalizedEmail:
    """Create NormalizedEmail from text."""
    lines = tuple(text.split("\n"))
    return NormalizedEmail(lines=lines, text=text)


def _make_labeling(labels: list[tuple[str, Label, float]]) -> SequenceLabelingResult:
    """Create a labeling result from (text, label, confidence) tuples."""
    labeled_lines = tuple(
        LabeledLine(
            text=text,
            label=label,
            confidence=conf,
            label_probabilities={label: conf},
        )
        for text, label, conf in labels
    )
    return SequenceLabelingResult(
        labeled_lines=labeled_lines,
        sequence_probability=0.9,
    )


class TestReconstructor:
    """Tests for document reconstruction."""

    def test_no_blanks_passthrough(self) -> None:
        """No blanks means labels pass through unchanged."""
        whitespace_map = WhitespaceMap(
            content_to_original=(0, 1, 2),
            blank_positions=frozenset(),
            original_line_count=3,
        )
        labeling = _make_labeling([
            ("Line 1", "BODY", 0.9),
            ("Line 2", "BODY", 0.8),
            ("Line 3", "CLOSING", 0.95),
        ])

        reconstructor = Reconstructor()
        result = reconstructor.reconstruct(
            labeling, whitespace_map, ("Line 1", "Line 2", "Line 3")
        )

        assert len(result.lines) == 3
        assert all(not line.is_blank for line in result.lines)
        assert result.lines[0].label == "BODY"
        assert result.lines[2].label == "CLOSING"

    def test_blank_lines_reinserted(self) -> None:
        """Blank lines are reinserted with is_blank=True."""
        whitespace_map = WhitespaceMap(
            content_to_original=(0, 2),
            blank_positions=frozenset({1}),
            original_line_count=3,
        )
        labeling = _make_labeling([
            ("Line 1", "BODY", 0.9),
            ("Line 2", "BODY", 0.8),
        ])

        reconstructor = Reconstructor()
        result = reconstructor.reconstruct(
            labeling, whitespace_map, ("Line 1", "", "Line 2")
        )

        assert len(result.lines) == 3
        assert result.lines[0].is_blank is False
        assert result.lines[1].is_blank is True
        assert result.lines[2].is_blank is False

    def test_blank_lines_have_no_label(self) -> None:
        """Blank lines have label=None."""
        whitespace_map = WhitespaceMap(
            content_to_original=(0, 2),
            blank_positions=frozenset({1}),
            original_line_count=3,
        )
        labeling = _make_labeling([
            ("Line 1", "BODY", 0.9),
            ("Line 2", "BODY", 0.8),
        ])

        reconstructor = Reconstructor()
        result = reconstructor.reconstruct(
            labeling, whitespace_map, ("Line 1", "", "Line 2")
        )

        assert result.lines[1].label is None
        assert result.lines[1].confidence is None
        assert result.lines[1].label_probabilities is None

    def test_original_index_correct(self) -> None:
        """All lines have correct original_index."""
        whitespace_map = WhitespaceMap(
            content_to_original=(0, 3),
            blank_positions=frozenset({1, 2}),
            original_line_count=4,
        )
        labeling = _make_labeling([
            ("A", "GREETING", 0.9),
            ("B", "BODY", 0.8),
        ])

        reconstructor = Reconstructor()
        result = reconstructor.reconstruct(
            labeling, whitespace_map, ("A", "", "", "B")
        )

        assert result.lines[0].original_index == 0
        assert result.lines[1].original_index == 1
        assert result.lines[2].original_index == 2
        assert result.lines[3].original_index == 3

    def test_leading_blanks(self) -> None:
        """Blank lines at start of document."""
        whitespace_map = WhitespaceMap(
            content_to_original=(2,),
            blank_positions=frozenset({0, 1}),
            original_line_count=3,
        )
        labeling = _make_labeling([
            ("Content", "BODY", 0.9),
        ])

        reconstructor = Reconstructor()
        result = reconstructor.reconstruct(
            labeling, whitespace_map, ("", "", "Content")
        )

        assert result.lines[0].is_blank is True
        assert result.lines[1].is_blank is True
        assert result.lines[2].is_blank is False
        assert result.lines[2].label == "BODY"

    def test_trailing_blanks(self) -> None:
        """Blank lines at end of document."""
        whitespace_map = WhitespaceMap(
            content_to_original=(0,),
            blank_positions=frozenset({1, 2}),
            original_line_count=3,
        )
        labeling = _make_labeling([
            ("Content", "BODY", 0.9),
        ])

        reconstructor = Reconstructor()
        result = reconstructor.reconstruct(
            labeling, whitespace_map, ("Content", "", "")
        )

        assert result.lines[0].label == "BODY"
        assert result.lines[1].is_blank is True
        assert result.lines[2].is_blank is True

    def test_sequence_probability_preserved(self) -> None:
        """sequence_probability is passed through."""
        whitespace_map = WhitespaceMap(
            content_to_original=(0,),
            blank_positions=frozenset(),
            original_line_count=1,
        )
        labeling = SequenceLabelingResult(
            labeled_lines=(
                LabeledLine(text="X", label="BODY", confidence=0.9, label_probabilities={"BODY": 0.9}),
            ),
            sequence_probability=0.75,
        )

        reconstructor = Reconstructor()
        result = reconstructor.reconstruct(labeling, whitespace_map, ("X",))

        assert result.sequence_probability == 0.75

    def test_text_preserved(self) -> None:
        """Original text is preserved including blank lines."""
        whitespace_map = WhitespaceMap(
            content_to_original=(0, 2),
            blank_positions=frozenset({1}),
            original_line_count=3,
        )
        labeling = _make_labeling([
            ("Hello", "GREETING", 0.9),
            ("World", "BODY", 0.8),
        ])

        reconstructor = Reconstructor()
        result = reconstructor.reconstruct(
            labeling, whitespace_map, ("Hello", "   ", "World")
        )

        assert result.lines[0].text == "Hello"
        assert result.lines[1].text == "   "  # Whitespace-only preserved
        assert result.lines[2].text == "World"


class TestRoundTrip:
    """Tests for filter -> reconstruct round trip."""

    def test_line_count_preserved(self) -> None:
        """Round trip preserves line count."""
        text = "A\n\nB\nC\n\nD"
        normalized = _make_normalized(text)

        filter_ = ContentFilter()
        filtered = filter_.filter(normalized)

        # Create fake labels for content lines
        labeling = _make_labeling([
            (line.text, "BODY", 0.9) for line in filtered.content_lines
        ])

        reconstructor = Reconstructor()
        result = reconstructor.reconstruct(
            labeling, filtered.whitespace_map, filtered.original_lines
        )

        assert len(result.lines) == 6  # A, blank, B, C, blank, D

    def test_blank_positions_match(self) -> None:
        """Round trip marks correct positions as blank."""
        text = "A\n\nB\n\n\nC"
        normalized = _make_normalized(text)

        filter_ = ContentFilter()
        filtered = filter_.filter(normalized)

        labeling = _make_labeling([
            (line.text, "BODY", 0.9) for line in filtered.content_lines
        ])

        reconstructor = Reconstructor()
        result = reconstructor.reconstruct(
            labeling, filtered.whitespace_map, filtered.original_lines
        )

        blank_indices = {line.original_index for line in result.lines if line.is_blank}
        assert blank_indices == {1, 3, 4}


class TestReconstructedLine:
    """Tests for ReconstructedLine structure."""

    def test_dataclass_frozen(self) -> None:
        """ReconstructedLine is immutable."""
        line = ReconstructedLine(
            text="Test",
            original_index=0,
            is_blank=False,
            label="BODY",
            confidence=0.9,
            label_probabilities={"BODY": 0.9},
        )
        try:
            line.text = "Changed"  # type: ignore[misc]
            assert False, "Should not allow mutation"
        except AttributeError:
            pass  # Expected
