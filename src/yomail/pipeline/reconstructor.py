"""Document reconstruction after CRF labeling.

Reinserts blank lines that were filtered out before ML processing.
"""

from dataclasses import dataclass

from yomail.pipeline.content_filter import WhitespaceMap
from yomail.pipeline.crf import Label, SequenceLabelingResult


@dataclass(frozen=True, slots=True)
class ReconstructedLine:
    """A line in the reconstructed document.

    Attributes:
        text: Line text.
        original_index: Position in the original document.
        is_blank: True if this was a blank line (filtered before ML).
        label: CRF-assigned label (None for blank lines).
        confidence: Marginal probability for the label (None for blank lines).
        label_probabilities: All label probabilities (None for blank lines).
    """

    text: str
    original_index: int
    is_blank: bool
    label: Label | None
    confidence: float | None
    label_probabilities: dict[Label, float] | None


@dataclass(frozen=True, slots=True)
class ReconstructedDocument:
    """Full document with all lines restored and labeled.

    Attributes:
        lines: All lines in original order (content + blank).
        sequence_probability: CRF sequence probability from labeling.
    """

    lines: tuple[ReconstructedLine, ...]
    sequence_probability: float


class Reconstructor:
    """Reconstructs full document from content-only labels.

    Blank lines are reinserted at their original positions with
    is_blank=True and no label.
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
        result: list[ReconstructedLine] = []
        content_idx = 0

        for orig_idx in range(whitespace_map.original_line_count):
            if orig_idx in whitespace_map.blank_positions:
                # Blank line - no label
                result.append(
                    ReconstructedLine(
                        text=original_lines[orig_idx],
                        original_index=orig_idx,
                        is_blank=True,
                        label=None,
                        confidence=None,
                        label_probabilities=None,
                    )
                )
            else:
                # Content line - use CRF result
                labeled = labeling.labeled_lines[content_idx]
                result.append(
                    ReconstructedLine(
                        text=labeled.text,
                        original_index=orig_idx,
                        is_blank=False,
                        label=labeled.label,
                        confidence=labeled.confidence,
                        label_probabilities=labeled.label_probabilities,
                    )
                )
                content_idx += 1

        return ReconstructedDocument(
            lines=tuple(result),
            sequence_probability=labeling.sequence_probability,
        )
