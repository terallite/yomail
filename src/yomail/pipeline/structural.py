"""Structural analysis for Japanese email text.

Analyzes the structure of normalized email text:
- Quote depth tracking (>, ＞, |, indentation)
- Quote block boundary detection
- Forward/reply header detection
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from yomail.patterns.separators import is_separator_line

if TYPE_CHECKING:
    from yomail.pipeline.content_filter import FilteredContent


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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


# Quote marker patterns (after normalization, ＞ becomes >)
# Match one or more quote markers at line start, optionally followed by space
_QUOTE_MARKER_PATTERN = re.compile(r"^([>|][\s>|]*)")

# Forward/reply header patterns
_FORWARD_REPLY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # English patterns
    re.compile(r"^-{3,}\s*Original\s+Message\s*-{3,}$", re.IGNORECASE),
    re.compile(r"^-{3,}\s*Forwarded\s+message\s*-{3,}$", re.IGNORECASE),
    re.compile(
        r"^On\s+\d{4}[/-]\d{1,2}[/-]\d{1,2}.*wrote:?\s*$", re.IGNORECASE
    ),
    re.compile(r"^On\s+.+wrote:?\s*$", re.IGNORECASE),
    # Japanese patterns
    re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日.*wrote:?\s*$"),
    re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日.*:$"),
    re.compile(r"^.*さんからのメール:?\s*$"),
    re.compile(r"^.*さんは.*に書きました:?\s*$"),
    re.compile(r"^転送:.*$"),
    re.compile(r"^Fwd:\s*.*$", re.IGNORECASE),
    re.compile(r"^Re:\s*.*$", re.IGNORECASE),
    # Outlook-style
    re.compile(r"^From:\s+.+$", re.IGNORECASE),  # When it's attribution, not header
    re.compile(r"^差出人:\s+.+$"),
    re.compile(r"^送信者:\s+.+$"),
    re.compile(r"^件名:\s+.+$"),
)



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
        content_lines = filtered.content_lines
        annotated: list[AnnotatedLine] = []

        first_quote_index: int | None = None
        last_quote_index: int | None = None
        has_forward_reply = False

        previous_is_delimiter = False

        for index, content_line in enumerate(content_lines):
            text = content_line.text
            quote_depth = self._compute_quote_depth(text)
            is_delimiter = self._is_delimiter_line(text)
            is_forward_reply_header = self._is_forward_reply_header(text)

            if is_forward_reply_header:
                has_forward_reply = True

            if quote_depth > 0:
                if first_quote_index is None:
                    first_quote_index = index
                last_quote_index = index

            annotated.append(
                AnnotatedLine(
                    text=text,
                    line_index=index,  # Content line index, not original
                    quote_depth=quote_depth,
                    is_forward_reply_header=is_forward_reply_header,
                    preceded_by_delimiter=previous_is_delimiter,
                    is_delimiter=is_delimiter,
                )
            )

            previous_is_delimiter = is_delimiter

        return StructuralAnalysis(
            lines=tuple(annotated),
            has_quotes=first_quote_index is not None,
            has_forward_reply=has_forward_reply,
            first_quote_index=first_quote_index,
            last_quote_index=last_quote_index,
        )

    def _compute_quote_depth(self, line: str) -> int:
        """Compute quote depth for a line.

        Counts the number of quote markers (> or |) at the start of the line.

        Args:
            line: A single line of text.

        Returns:
            Quote depth (0 if not quoted).
        """
        match = _QUOTE_MARKER_PATTERN.match(line)
        if not match:
            return 0

        # Count the number of > or | characters in the matched prefix
        prefix = match.group(1)
        return sum(1 for char in prefix if char in ">|")

    def _is_delimiter_line(self, line: str) -> bool:
        """Check if a line is a visual delimiter.

        Delimiter lines are used to separate sections of an email,
        often before signatures or quoted content.

        Args:
            line: A single line of text.

        Returns:
            True if the line is a visual delimiter.
        """
        return is_separator_line(line)

    def _is_forward_reply_header(self, line: str) -> bool:
        """Check if a line is a forward/reply attribution header.

        These are lines like "On 2024/01/01, John wrote:" that
        introduce quoted content in replies.

        Args:
            line: A single line of text.

        Returns:
            True if the line is a forward/reply header.
        """
        stripped = line.strip()
        if not stripped:
            return False

        return any(pattern.match(stripped) for pattern in _FORWARD_REPLY_PATTERNS)
