"""Type stubs for yomail.extractor."""

from pathlib import Path

from yomail.exceptions import ExtractionError
from yomail.pipeline.crf import LabeledLine

class ExtractionResult:
    """Full extraction result with metadata.

    Attributes:
        body: Extracted body text, or None if extraction failed.
        confidence: Confidence score (0.0 to 1.0).
        success: Whether extraction succeeded.
        error: Error if extraction failed, None otherwise.
        labeled_lines: All lines with their labels (for debugging).
        signature_detected: Whether a signature was found.
        inline_quotes_included: Number of inline quote lines in body.
    """
    body: str | None
    confidence: float
    success: bool
    error: ExtractionError | None
    labeled_lines: tuple[LabeledLine, ...]
    signature_detected: bool
    inline_quotes_included: int
    def __init__(
        self,
        body: str | None,
        confidence: float,
        success: bool,
        error: ExtractionError | None,
        labeled_lines: tuple[LabeledLine, ...],
        signature_detected: bool,
        inline_quotes_included: int,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class EmailBodyExtractor:
    """Main class for extracting body text from Japanese emails.

    The extraction pipeline:
    1. Normalize text (encoding, Unicode, headers)
    2. Analyze structure (quotes, delimiters)
    3. Extract features for CRF
    4. Label lines with CRF model
    5. Assemble body from labeled lines
    6. Validate confidence

    Example:
        extractor = EmailBodyExtractor()

        # Strict extraction (raises on failure)
        body = extractor.extract(email_text)

        # Safe extraction (returns None on failure)
        body = extractor.extract_safe(email_text)

        # Full metadata
        result = extractor.extract_with_metadata(email_text)
    """
    def __init__(
        self,
        model_path: Path | str | None = None,
        confidence_threshold: float = 0.5,
    ) -> None:
        """Initialize the extractor.

        Args:
            model_path: Path to trained CRF model. If None, uses the bundled model.
            confidence_threshold: Minimum confidence to accept extraction.
        """
        ...
    def load_model(self, model_path: Path | str) -> None:
        """Load a CRF model.

        Args:
            model_path: Path to the model file.
        """
        ...
    @property
    def is_model_loaded(self) -> bool:
        """Whether a model is currently loaded."""
        ...
    def extract(self, email_text: str) -> str:
        """Extract body text from an email.

        Args:
            email_text: Raw email text (headers optional, body required).

        Returns:
            Extracted body text.

        Raises:
            InvalidInputError: If input is empty or invalid.
            NoBodyDetectedError: If no body content found.
            LowConfidenceError: If confidence is below threshold.
            RuntimeError: If no model is loaded.
        """
        ...
    def extract_safe(self, email_text: str) -> str | None:
        """Extract body text, returning None on any failure.

        Args:
            email_text: Raw email text.

        Returns:
            Extracted body text, or None if extraction failed.
        """
        ...
    def extract_with_metadata(self, email_text: str) -> ExtractionResult:
        """Extract body with full metadata.

        Args:
            email_text: Raw email text.

        Returns:
            ExtractionResult with body, confidence, and debugging info.
        """
        ...
