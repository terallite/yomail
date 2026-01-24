"""Text normalization for Japanese emails.

Handles:
- Line ending normalization
- Japanese text normalization (neologdn + NFKC)
- RFC 2822 header stripping
"""

import re
import unicodedata
from dataclasses import dataclass

import neologdn

from yomail.exceptions import InvalidInputError

# RFC 2822 header pattern: field name followed by colon
# Header names are ASCII alphanumeric plus hyphen, case-insensitive
_HEADER_LINE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:\s*")

# Continuation line: starts with whitespace (folded header)
_CONTINUATION_PATTERN = re.compile(r"^[ \t]+\S")

# Common email headers to recognize
_KNOWN_HEADERS = frozenset(
    {
        "from",
        "to",
        "cc",
        "bcc",
        "subject",
        "date",
        "message-id",
        "in-reply-to",
        "references",
        "reply-to",
        "sender",
        "return-path",
        "received",
        "mime-version",
        "content-type",
        "content-transfer-encoding",
        "content-disposition",
        "x-mailer",
        "x-originating-ip",
        "x-priority",
    }
)


@dataclass(frozen=True, slots=True)
class NormalizedEmail:
    """Result of normalizing an email.

    Attributes:
        lines: List of normalized lines (without line endings).
        text: Full normalized text with newlines.
        headers_stripped: Whether RFC 2822 headers were detected and removed.
    """

    lines: tuple[str, ...]
    text: str
    headers_stripped: bool


class Normalizer:
    """Normalizes Japanese email text for downstream processing.

    Applies the following transformations:
    1. Line ending normalization (CRLF/CR → LF)
    2. neologdn normalization (Japanese-specific)
    3. Unicode NFKC normalization
    4. RFC 2822 header stripping (optional)
    """

    def __init__(self, *, strip_headers: bool = True) -> None:
        """Initialize the normalizer.

        Args:
            strip_headers: If True, detect and remove RFC 2822 headers.
        """
        self._strip_headers = strip_headers

    def normalize(self, text: str) -> NormalizedEmail:
        """Normalize email text.

        Args:
            text: Raw email text (UTF-8 string).

        Returns:
            NormalizedEmail with normalized lines and text.

        Raises:
            InvalidInputError: If text is empty after normalization.
        """
        # Normalize line endings: CRLF and CR to LF
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Strip headers if enabled
        headers_stripped = False
        if self._strip_headers:
            text, headers_stripped = self._strip_rfc2822_headers(text)

        # Apply Japanese text normalization
        text = self._normalize_japanese(text)

        # Split into lines
        lines = text.split("\n")

        # Check for empty result
        if not lines or all(line.strip() == "" for line in lines):
            raise InvalidInputError(message="Empty input after normalization")

        return NormalizedEmail(
            lines=tuple(lines),
            text=text,
            headers_stripped=headers_stripped,
        )

    def _normalize_japanese(self, text: str) -> str:
        """Apply Japanese-specific normalization.

        Uses neologdn followed by NFKC normalization.

        neologdn handles:
        - Full-width ASCII → half-width (Ａ→A, １→1)
        - Half-width katakana → full-width (ｶﾀｶﾅ→カタカナ)
        - Repeated prolonged sound marks (ーーー→ー)
        - Tilde/wave dash variants

        NFKC handles remaining Unicode compatibility decomposition.
        """
        # neologdn first (Japanese-specific normalization)
        text = neologdn.normalize(text)

        # NFKC for remaining Unicode normalization
        text = unicodedata.normalize("NFKC", text)

        return text

    def _strip_rfc2822_headers(self, text: str) -> tuple[str, bool]:
        """Remove RFC 2822 headers from email text.

        Headers are at the start of the message and end at the first
        blank line. Each header is a field name, colon, and value.
        Headers may be folded (continued on next line with leading whitespace).

        Args:
            text: Email text potentially containing headers.

        Returns:
            Tuple of (text with headers removed, whether headers were found).
        """
        lines = text.split("\n")
        if not lines:
            return text, False

        # Look for header block at the start
        header_end_index = self._find_header_end(lines)

        if header_end_index == 0:
            # No headers found
            return text, False

        # Skip the blank line after headers too
        body_start = header_end_index
        if body_start < len(lines) and lines[body_start].strip() == "":
            body_start += 1

        # Reconstruct body
        body_lines = lines[body_start:]
        return "\n".join(body_lines), True

    def _find_header_end(self, lines: list[str]) -> int:
        """Find where headers end in the line list.

        Returns the index of the first non-header line (the blank separator),
        or 0 if no valid header block is found.
        """
        if not lines:
            return 0

        # First line must look like a header
        first_line = lines[0]
        if not self._is_header_line(first_line):
            return 0

        in_header_block = True
        index = 0

        while index < len(lines) and in_header_block:
            line = lines[index]

            # Blank line ends header block
            if line.strip() == "":
                return index

            # Check if this is a header or continuation
            if self._is_header_line(line):
                index += 1
            elif _CONTINUATION_PATTERN.match(line):
                # Folded header continuation
                index += 1
            else:
                # Not a header and not a continuation - no valid header block
                return 0

        # Reached end of text while still in headers (unusual but valid)
        return index

    def _is_header_line(self, line: str) -> bool:
        """Check if a line looks like an RFC 2822 header."""
        match = _HEADER_LINE_PATTERN.match(line)
        if not match:
            return False

        # Extract header name and check if it's known
        # This helps avoid false positives on Japanese text with colons
        colon_pos = line.find(":")
        if colon_pos == -1:
            return False

        header_name = line[:colon_pos].lower()
        return header_name in _KNOWN_HEADERS
