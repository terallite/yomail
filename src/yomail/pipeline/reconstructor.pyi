"""Type stubs for yomail.pipeline.reconstructor."""

from yomail.pipeline.content_filter import WhitespaceMap
from yomail.pipeline.crf import Label, SequenceLabelingResult

class ReconstructedLine:
    """A line in the reconstructed document.

    Attributes:
        text: Line text.
        original_index: Position in the original document.
        is_blank: True if this was a blank line (filtered before ML).
        label: CRF-assigned label. Blank lines inherit the preceding content
            line's label (or None if at document start with no prior content).
        confidence: Marginal probability for the label (None for blank lines).
        label_probabilities: All label probabilities (None for blank lines).
    """
    text: str
    original_index: int
    is_blank: bool
    label: Label | None
    confidence: float | None
    label_probabilities: dict[Label, float] | None
    def __init__(
        self,
        text: str,
        original_index: int,
        is_blank: bool,
        label: Label | None,
        confidence: float | None,
        label_probabilities: dict[Label, float] | None,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class ReconstructedDocument:
    """Full document with all lines restored and labeled.

    Attributes:
        lines: All lines in original order (content + blank).
        sequence_probability: CRF sequence probability from labeling.
    """
    lines: tuple[ReconstructedLine, ...]
    sequence_probability: float
    def __init__(
        self, lines: tuple[ReconstructedLine, ...], sequence_probability: float
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class Reconstructor:
    """Reconstructs full document from content-only labels.

    Blank lines are reinserted at their original positions with
    is_blank=True. They inherit the preceding content line's label
    to maintain context through whitespace.
    """
    def reconstruct(
        self,
        labeling: SequenceLabelingResult,
        whitespace_map: WhitespaceMap,
        original_lines: tuple[str, ...],
    ) -> ReconstructedDocument:
        """Reinsert blank lines into labeled sequence.

        Args:
            labeling: CRF labeling result (content lines only).
            whitespace_map: Mapping from content filter.
            original_lines: Original line texts.

        Returns:
            ReconstructedDocument with all lines in original order.
        """
        ...
