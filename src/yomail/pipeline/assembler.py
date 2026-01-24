"""Body Assembler for extracting the final email body from labeled lines.

Takes CRF-labeled lines and assembles them into the final body text:
- Finds signature boundary and excludes content after it
- Classifies quotes as inline vs trailing/leading
- Builds content blocks with merging logic
- Selects the appropriate body region
"""

import logging
from dataclasses import dataclass

from yomail.pipeline.crf import LabeledLine, SequenceLabelingResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
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


class BodyAssembler:
    """Assembles the final body text from CRF-labeled lines.

    Implements the assembly logic from DESIGN.md section 3.5:
    1. Find signature boundary
    2. Classify inline vs trailing quotes
    3. Build content blocks
    4. Select final body
    5. Assemble text
    """

    def assemble(self, labeling_result: SequenceLabelingResult) -> AssembledBody:
        """Assemble body text from labeled lines.

        Args:
            labeling_result: Output from CRFSequenceLabeler.

        Returns:
            AssembledBody with extracted text and metadata.
        """
        labeled_lines = labeling_result.labeled_lines

        if not labeled_lines:
            return AssembledBody(
                body_text="",
                body_lines=(),
                signature_index=None,
                inline_quote_count=0,
                success=False,
            )

        # Step 1: Find signature boundary
        signature_index = self._find_signature_boundary(labeled_lines)

        # Step 2: Identify inline vs trailing/leading quotes
        inline_quote_indices = self._find_inline_quotes(labeled_lines, signature_index)

        # Step 3: Build content blocks
        blocks = self._build_content_blocks(labeled_lines, signature_index, inline_quote_indices)

        # Step 4: Select final body
        selected_indices = self._select_body(blocks, signature_index)

        # Step 5: Assemble text
        body_text = self._assemble_text(labeled_lines, selected_indices)

        # Count inline quotes in selected body
        inline_quote_count = sum(1 for idx in selected_indices if idx in inline_quote_indices)

        return AssembledBody(
            body_text=body_text,
            body_lines=tuple(selected_indices),
            signature_index=signature_index,
            inline_quote_count=inline_quote_count,
            success=len(body_text.strip()) > 0,
        )

    def _find_signature_boundary(self, labeled_lines: tuple[LabeledLine, ...]) -> int | None:
        """Find the index of the first SIGNATURE line.

        All content from this line onward is excluded from body consideration.

        Args:
            labeled_lines: Sequence of labeled lines.

        Returns:
            Index of first SIGNATURE line, or None if no signature found.
        """
        for idx, line in enumerate(labeled_lines):
            if line.label == "SIGNATURE":
                return idx
        return None

    def _find_inline_quotes(
        self,
        labeled_lines: tuple[LabeledLine, ...],
        signature_index: int | None,
    ) -> set[int]:
        """Find indices of inline quote lines.

        A QUOTE line is "inline" if there exists BODY-labeled content
        both before AND after it (within the pre-signature region).

        Args:
            labeled_lines: Sequence of labeled lines.
            signature_index: Index of signature boundary, or None.

        Returns:
            Set of indices for inline quote lines.
        """
        # Determine the range to consider (up to but not including signature)
        end_index = signature_index if signature_index is not None else len(labeled_lines)

        # Find all BODY line indices in the range
        body_indices: list[int] = []
        for idx in range(end_index):
            if labeled_lines[idx].label == "BODY":
                body_indices.append(idx)

        if len(body_indices) < 2:
            # Need at least 2 BODY lines to have something before and after a quote
            return set()

        first_body = body_indices[0]
        last_body = body_indices[-1]

        # Find QUOTE lines that are between first and last BODY lines
        inline_quotes: set[int] = set()
        for idx in range(end_index):
            if labeled_lines[idx].label == "QUOTE":
                if first_body < idx < last_body:
                    inline_quotes.add(idx)

        return inline_quotes

    def _build_content_blocks(
        self,
        labeled_lines: tuple[LabeledLine, ...],
        signature_index: int | None,
        inline_quote_indices: set[int],
    ) -> list[list[int]]:
        """Build content blocks from labeled lines.

        Block building rules:
        - BODY lines accumulate into current block
        - SEPARATOR lines are buffered; included if followed by more BODY
        - Inline QUOTE lines are included in current block
        - GREETING and CLOSING lines are included if adjacent to BODY
        - OTHER lines create hard breaks between blocks
        - Trailing/leading QUOTE lines create hard breaks

        Args:
            labeled_lines: Sequence of labeled lines.
            signature_index: Index of signature boundary, or None.
            inline_quote_indices: Set of inline quote indices.

        Returns:
            List of blocks, where each block is a list of line indices.
        """
        end_index = signature_index if signature_index is not None else len(labeled_lines)

        blocks: list[list[int]] = []
        current_block: list[int] = []
        separator_buffer: list[int] = []

        for idx in range(end_index):
            line = labeled_lines[idx]
            label = line.label

            if label == "BODY":
                # Flush separator buffer - separators before BODY are included
                current_block.extend(separator_buffer)
                separator_buffer = []
                current_block.append(idx)

            elif label == "SEPARATOR":
                # Buffer separators - only include if followed by more BODY
                separator_buffer.append(idx)

            elif label == "QUOTE":
                if idx in inline_quote_indices:
                    # Inline quote - include in current block
                    current_block.extend(separator_buffer)
                    separator_buffer = []
                    current_block.append(idx)
                else:
                    # Trailing/leading quote - hard break
                    if current_block:
                        blocks.append(current_block)
                        current_block = []
                    separator_buffer = []

            elif label in ("GREETING", "CLOSING"):
                # Include if adjacent to BODY (i.e., current block is non-empty
                # or will become non-empty soon)
                # Strategy: include them, they'll be part of the block
                current_block.extend(separator_buffer)
                separator_buffer = []
                current_block.append(idx)

            elif label == "OTHER":
                # Hard break
                if current_block:
                    blocks.append(current_block)
                    current_block = []
                separator_buffer = []

            # Note: We don't handle SIGNATURE here as we stop at signature_index

        # Flush remaining block (but not separator buffer - trailing separators dropped)
        if current_block:
            blocks.append(current_block)

        return blocks

    def _select_body(
        self,
        blocks: list[list[int]],
        signature_index: int | None,
    ) -> list[int]:
        """Select the final body from content blocks.

        Selection rules:
        - If signature was detected: concatenate all blocks before signature
        - If no signature detected: select the longest block (by line count)
        - Multiple equally-long blocks: take the first one

        Args:
            blocks: List of content blocks (each block is a list of line indices).
            signature_index: Index of signature boundary, or None.

        Returns:
            List of line indices for the selected body.
        """
        if not blocks:
            return []

        if signature_index is not None:
            # Concatenate all blocks (they're already before signature)
            result: list[int] = []
            for block in blocks:
                result.extend(block)
            return result
        else:
            # Select longest block (first one wins ties)
            longest_block: list[int] = []
            for block in blocks:
                if len(block) > len(longest_block):
                    longest_block = block
            return longest_block

    def _assemble_text(
        self,
        labeled_lines: tuple[LabeledLine, ...],
        selected_indices: list[int],
    ) -> str:
        """Assemble final text from selected line indices.

        Preserves original line breaks by joining with newlines.

        Args:
            labeled_lines: Sequence of labeled lines.
            selected_indices: Indices of lines to include.

        Returns:
            Assembled body text.
        """
        if not selected_indices:
            return ""

        lines = [labeled_lines[idx].text for idx in selected_indices]
        return "\n".join(lines)
