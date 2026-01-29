"""Type stubs for yomail.pipeline.structural."""

from yomail.pipeline.content_filter import FilteredContent

class AnnotatedLine:
    """A line with structural annotations.

    Attributes:
        text: Original line text.
        line_index: Zero-based position in the email.
        quote_depth: Nesting level of quoting (0 = not quoted).
        is_forward_reply_header: Line is a forward/reply attribution header.
        preceded_by_delimiter: A visual delimiter line immediately precedes this line.
        is_delimiter: Line itself is a visual delimiter.
    """
    text: str
    line_index: int
    quote_depth: int
    is_forward_reply_header: bool
    preceded_by_delimiter: bool
    is_delimiter: bool
    def __init__(
        self,
        text: str,
        line_index: int,
        quote_depth: int,
        is_forward_reply_header: bool,
        preceded_by_delimiter: bool,
        is_delimiter: bool,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class StructuralAnalysis:
    """Result of structural analysis on an email.

    Attributes:
        lines: Tuple of annotated lines.
        has_quotes: Whether the email contains any quoted content.
        has_forward_reply: Whether forward/reply headers were detected.
        first_quote_index: Index of first quoted line, or None.
        last_quote_index: Index of last quoted line, or None.
    """
    lines: tuple[AnnotatedLine, ...]
    has_quotes: bool
    has_forward_reply: bool
    first_quote_index: int | None
    last_quote_index: int | None
    def __init__(
        self,
        lines: tuple[AnnotatedLine, ...],
        has_quotes: bool,
        has_forward_reply: bool,
        first_quote_index: int | None,
        last_quote_index: int | None,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class StructuralAnalyzer:
    """Analyzes email structure for quote detection and segmentation.

    Processes content-only lines (blank lines filtered) to identify:
    - Quote depth per line (from markers like > or |)
    - Forward/reply attribution headers
    - Visual delimiter lines that separate sections
    """
    def analyze(self, filtered: FilteredContent) -> StructuralAnalysis:
        """Analyze structural elements of content-only lines.

        Args:
            filtered: Output from ContentFilter.

        Returns:
            StructuralAnalysis with annotated content lines.
        """
        ...
