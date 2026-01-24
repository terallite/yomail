"""Text normalization for Japanese emails.

Handles:
- Line ending normalization
- Japanese text normalization (neologdn + NFKC)
"""

import unicodedata
from dataclasses import dataclass

import neologdn

from yomail.exceptions import InvalidInputError


@dataclass(frozen=True, slots=True)
class NormalizedEmail:
    """Result of normalizing an email.

    Attributes:
        lines: List of normalized lines (without line endings).
        text: Full normalized text with newlines.
    """

    lines: tuple[str, ...]
    text: str


class Normalizer:
    """Normalizes Japanese email text for downstream processing.

    Applies the following transformations:
    1. Line ending normalization (CRLF/CR → LF)
    2. neologdn normalization (Japanese-specific)
    3. Unicode NFKC normalization
    """

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
