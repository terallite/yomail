"""Type stubs for yomail.pipeline.normalizer."""

class NormalizedEmail:
    """Result of normalizing an email.

    Attributes:
        lines: List of normalized lines (without line endings).
        text: Full normalized text with newlines.
    """
    lines: tuple[str, ...]
    text: str
    def __init__(self, lines: tuple[str, ...], text: str) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

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
        ...
