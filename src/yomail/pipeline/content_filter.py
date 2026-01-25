"""Content filtering for CRF sequence labeling.

Separates blank lines from content lines before ML processing.
Blank lines are reinserted after labeling using the WhitespaceMap.
"""

from dataclasses import dataclass, replace

from yomail.pipeline.normalizer import NormalizedEmail


@dataclass(frozen=True, slots=True)
class ContentLine:
    """A non-blank line with whitespace context.

    Attributes:
        text: The line text (never empty/whitespace-only).
        original_index: Position in the original document.
        blank_lines_before: Count of blank lines immediately before this line.
        blank_lines_after: Count of blank lines immediately after this line.
    """

    text: str
    original_index: int
    blank_lines_before: int
    blank_lines_after: int


@dataclass(frozen=True, slots=True)
class WhitespaceMap:
    """Mapping from content line indices to original line indices.

    Used to reconstruct the full document after CRF labeling.

    Attributes:
        content_to_original: Maps content line index to original line index.
        blank_positions: Set of original line indices that are blank.
        original_line_count: Total number of lines in the original document.
    """

    content_to_original: tuple[int, ...]
    blank_positions: frozenset[int]
    original_line_count: int


@dataclass(frozen=True, slots=True)
class FilteredContent:
    """Result of content filtering.

    Attributes:
        content_lines: Tuple of ContentLine objects (non-blank lines only).
        whitespace_map: Mapping for reconstruction.
        original_lines: Original lines for reconstruction.
    """

    content_lines: tuple[ContentLine, ...]
    whitespace_map: WhitespaceMap
    original_lines: tuple[str, ...]


class ContentFilter:
    """Separates content lines from blank lines.

    Blank lines (empty or whitespace-only) are filtered out before
    feature extraction and CRF labeling. They are tracked in a
    WhitespaceMap for reconstruction after labeling.
    """

    def filter(self, normalized: NormalizedEmail) -> FilteredContent:
        """Extract content lines and build whitespace map.

        Args:
            normalized: Output from Normalizer.

        Returns:
            FilteredContent with content lines and whitespace map.
        """
        content_lines: list[ContentLine] = []
        blank_positions: set[int] = set()
        content_to_original: list[int] = []

        # First pass: identify content vs blank, track blank_lines_before
        pending_blanks = 0

        for orig_idx, text in enumerate(normalized.lines):
            if text.strip():
                # Content line
                content_lines.append(
                    ContentLine(
                        text=text,
                        original_index=orig_idx,
                        blank_lines_before=pending_blanks,
                        blank_lines_after=0,  # Set in second pass
                    )
                )
                content_to_original.append(orig_idx)
                pending_blanks = 0
            else:
                # Blank line (empty or whitespace-only)
                blank_positions.add(orig_idx)
                pending_blanks += 1

        # Second pass: set blank_lines_after for each content line
        for i in range(len(content_lines) - 1):
            curr_orig = content_lines[i].original_index
            next_orig = content_lines[i + 1].original_index
            blanks_between = next_orig - curr_orig - 1
            content_lines[i] = replace(content_lines[i], blank_lines_after=blanks_between)

        # Last content line: count trailing blanks
        if content_lines:
            last_orig = content_lines[-1].original_index
            trailing_blanks = len(normalized.lines) - last_orig - 1
            content_lines[-1] = replace(content_lines[-1], blank_lines_after=trailing_blanks)

        return FilteredContent(
            content_lines=tuple(content_lines),
            whitespace_map=WhitespaceMap(
                content_to_original=tuple(content_to_original),
                blank_positions=frozenset(blank_positions),
                original_line_count=len(normalized.lines),
            ),
            original_lines=normalized.lines,
        )
