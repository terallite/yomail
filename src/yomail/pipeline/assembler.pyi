"""Type stubs for yomail.pipeline.assembler."""

from yomail.pipeline.reconstructor import ReconstructedDocument

class AssembledBody:
    """Result of body assembly.

    Attributes:
        body_text: The extracted body text (may be empty string if no body found).
        body_lines: Indices of lines included in the body.
        signature_index: Index of first signature line, or None if no signature.
        inline_quote_count: Number of inline quote lines included in body.
        success: Whether body extraction succeeded (non-empty body).
    """
    body_text: str
    body_lines: tuple[int, ...]
    signature_index: int | None
    inline_quote_count: int
    success: bool
    def __init__(
        self,
        body_text: str,
        body_lines: tuple[int, ...],
        signature_index: int | None,
        inline_quote_count: int,
        success: bool,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class BodyAssembler:
    """Assembles the final body text from CRF-labeled lines.

    Implements the assembly logic:
    1. Find signature boundary
    2. Classify inline vs trailing quotes
    3. Build content blocks
    4. Select final body
    5. Assemble text
    """
    def assemble(self, doc: ReconstructedDocument) -> AssembledBody:
        """Assemble body text from labeled lines.

        Args:
            doc: ReconstructedDocument with all lines (content + blank) labeled.

        Returns:
            AssembledBody with extracted text and metadata.
        """
        ...
