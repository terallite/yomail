"""Type stubs for yomail.pipeline.content_filter."""

from yomail.pipeline.normalizer import NormalizedEmail

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
    def __init__(
        self,
        text: str,
        original_index: int,
        blank_lines_before: int,
        blank_lines_after: int,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

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
    def __init__(
        self,
        content_to_original: tuple[int, ...],
        blank_positions: frozenset[int],
        original_line_count: int,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

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
    def __init__(
        self,
        content_lines: tuple[ContentLine, ...],
        whitespace_map: WhitespaceMap,
        original_lines: tuple[str, ...],
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

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
        ...
