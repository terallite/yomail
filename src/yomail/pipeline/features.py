"""Feature extraction for CRF sequence labeling.

Extracts per-line features from structurally analyzed email text:
- Positional features (normalized position, distance from start/end)
- Content features (length, character class ratios, whitespace)
- Pattern flags (greeting, closing, contact info, etc.)
- Contextual features (aggregates from surrounding lines)
"""

import re
import unicodedata
from dataclasses import dataclass

from yomail.patterns.closings import is_closing_line
from yomail.patterns.greetings import is_greeting_line
from yomail.patterns.signatures import (
    is_company_line,
    is_contact_info_line,
    is_position_line,
    is_visual_separator_line,
)
from yomail.pipeline.structural import AnnotatedLine, StructuralAnalysis


@dataclass(frozen=True, slots=True)
class LineFeatures:
    """Feature vector for a single line.

    All numeric features are normalized to [0, 1] where applicable.
    Boolean features are stored as bool (converted to 0/1 for CRF).
    """

    # Positional features
    position_normalized: float  # 0.0 (start) to 1.0 (end)
    position_reverse: float  # 1.0 (start) to 0.0 (end)
    lines_from_start: int
    lines_from_end: int
    position_rel_first_quote: float  # Negative if before, positive if after
    position_rel_last_quote: float

    # Content features
    line_length: int
    kanji_ratio: float
    hiragana_ratio: float
    katakana_ratio: float
    ascii_ratio: float
    digit_ratio: float
    symbol_ratio: float
    leading_whitespace: int
    trailing_whitespace: int
    is_blank: bool

    # Structural features (from StructuralAnalyzer)
    quote_depth: int
    is_forward_reply_header: bool
    preceded_by_delimiter: bool
    is_delimiter: bool

    # Pattern flags
    is_greeting: bool
    is_closing: bool
    has_contact_info: bool
    has_company_pattern: bool
    has_position_pattern: bool
    is_visual_separator: bool
    has_meta_discussion: bool
    is_inside_quotation_marks: bool

    # Contextual features (window ±2 lines)
    context_greeting_count: int
    context_closing_count: int
    context_contact_count: int
    context_blank_count: int
    context_quote_count: int
    context_separator_count: int


@dataclass(frozen=True, slots=True)
class ExtractedFeatures:
    """Result of feature extraction for an entire email.

    Attributes:
        line_features: Tuple of LineFeatures, one per line.
        total_lines: Total number of lines in the email.
    """

    line_features: tuple[LineFeatures, ...]
    total_lines: int


# Meta-discussion patterns - lines discussing examples or quoted content
_META_DISCUSSION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"例えば"),
    re.compile(r"以下の"),
    re.compile(r"下記の"),
    re.compile(r"次の"),
    re.compile(r"サンプル"),
    re.compile(r"具体例"),
    re.compile(r"参考まで"),
    re.compile(r"添付の"),
    re.compile(r"上記の"),
    re.compile(r"前述の"),
)

# Japanese quotation mark pairs
_QUOTATION_PAIRS = (
    ("「", "」"),
    ("『", "』"),
    (""", """),
    ("\"", "\""),
)


class FeatureExtractor:
    """Extracts features from structurally analyzed email text.

    Features are designed for CRF sequence labeling to classify
    each line as GREETING, BODY, CLOSING, SIGNATURE, QUOTE, SEPARATOR, or OTHER.
    """

    def extract(self, analysis: StructuralAnalysis) -> ExtractedFeatures:
        """Extract features from structurally analyzed email.

        Args:
            analysis: Output from StructuralAnalyzer.

        Returns:
            ExtractedFeatures with per-line feature vectors.
        """
        lines = analysis.lines
        total_lines = len(lines)

        if total_lines == 0:
            return ExtractedFeatures(line_features=(), total_lines=0)

        # Pre-compute per-line pattern flags for contextual features
        line_flags = [self._compute_pattern_flags(line) for line in lines]

        # Build feature vectors
        feature_list: list[LineFeatures] = []

        for idx, annotated_line in enumerate(lines):
            features = self._extract_line_features(
                annotated_line=annotated_line,
                idx=idx,
                total_lines=total_lines,
                first_quote_index=analysis.first_quote_index,
                last_quote_index=analysis.last_quote_index,
                all_lines=lines,
                all_flags=line_flags,
            )
            feature_list.append(features)

        return ExtractedFeatures(
            line_features=tuple(feature_list),
            total_lines=total_lines,
        )

    def _extract_line_features(
        self,
        annotated_line: AnnotatedLine,
        idx: int,
        total_lines: int,
        first_quote_index: int | None,
        last_quote_index: int | None,
        all_lines: tuple[AnnotatedLine, ...],
        all_flags: list[dict[str, bool]],
    ) -> LineFeatures:
        """Extract features for a single line."""
        text = annotated_line.text

        # Positional features
        position_normalized = idx / max(total_lines - 1, 1)
        position_reverse = 1.0 - position_normalized
        lines_from_start = idx
        lines_from_end = total_lines - 1 - idx

        # Position relative to quote blocks
        if first_quote_index is not None:
            position_rel_first_quote = (idx - first_quote_index) / max(total_lines, 1)
        else:
            position_rel_first_quote = 0.0

        if last_quote_index is not None:
            position_rel_last_quote = (idx - last_quote_index) / max(total_lines, 1)
        else:
            position_rel_last_quote = 0.0

        # Content features
        line_length = len(text)
        char_ratios = self._compute_character_ratios(text)
        leading_whitespace = len(text) - len(text.lstrip())
        trailing_whitespace = len(text) - len(text.rstrip())
        is_blank = text.strip() == ""

        # Pattern flags
        flags = all_flags[idx]

        # Contextual features (window ±2)
        context = self._compute_context_features(idx, all_lines, all_flags)

        return LineFeatures(
            # Positional
            position_normalized=position_normalized,
            position_reverse=position_reverse,
            lines_from_start=lines_from_start,
            lines_from_end=lines_from_end,
            position_rel_first_quote=position_rel_first_quote,
            position_rel_last_quote=position_rel_last_quote,
            # Content
            line_length=line_length,
            kanji_ratio=char_ratios["kanji"],
            hiragana_ratio=char_ratios["hiragana"],
            katakana_ratio=char_ratios["katakana"],
            ascii_ratio=char_ratios["ascii"],
            digit_ratio=char_ratios["digit"],
            symbol_ratio=char_ratios["symbol"],
            leading_whitespace=leading_whitespace,
            trailing_whitespace=trailing_whitespace,
            is_blank=is_blank,
            # Structural (from AnnotatedLine)
            quote_depth=annotated_line.quote_depth,
            is_forward_reply_header=annotated_line.is_forward_reply_header,
            preceded_by_delimiter=annotated_line.preceded_by_delimiter,
            is_delimiter=annotated_line.is_delimiter,
            # Pattern flags
            is_greeting=flags["is_greeting"],
            is_closing=flags["is_closing"],
            has_contact_info=flags["has_contact_info"],
            has_company_pattern=flags["has_company_pattern"],
            has_position_pattern=flags["has_position_pattern"],
            is_visual_separator=flags["is_visual_separator"],
            has_meta_discussion=flags["has_meta_discussion"],
            is_inside_quotation_marks=flags["is_inside_quotation_marks"],
            # Contextual
            context_greeting_count=context["greeting_count"],
            context_closing_count=context["closing_count"],
            context_contact_count=context["contact_count"],
            context_blank_count=context["blank_count"],
            context_quote_count=context["quote_count"],
            context_separator_count=context["separator_count"],
        )

    def _compute_pattern_flags(self, annotated_line: AnnotatedLine) -> dict[str, bool]:
        """Compute pattern flags for a line."""
        text = annotated_line.text

        return {
            "is_greeting": is_greeting_line(text),
            "is_closing": is_closing_line(text),
            "has_contact_info": is_contact_info_line(text),
            "has_company_pattern": is_company_line(text),
            "has_position_pattern": is_position_line(text),
            "is_visual_separator": is_visual_separator_line(text),
            "has_meta_discussion": self._has_meta_discussion(text),
            "is_inside_quotation_marks": self._is_inside_quotation_marks(text),
            "is_blank": text.strip() == "",
        }

    def _compute_character_ratios(self, text: str) -> dict[str, float]:
        """Compute character class ratios for a line.

        Returns ratios for: kanji, hiragana, katakana, ascii, digit, symbol.
        """
        if not text:
            return {
                "kanji": 0.0,
                "hiragana": 0.0,
                "katakana": 0.0,
                "ascii": 0.0,
                "digit": 0.0,
                "symbol": 0.0,
            }

        counts = {
            "kanji": 0,
            "hiragana": 0,
            "katakana": 0,
            "ascii": 0,
            "digit": 0,
            "symbol": 0,
        }

        for char in text:
            category = self._classify_character(char)
            counts[category] += 1

        total = len(text)
        return {key: count / total for key, count in counts.items()}

    def _classify_character(self, char: str) -> str:
        """Classify a character into one of the tracked categories."""
        # Check ASCII first (most common in mixed text)
        if char.isascii():
            if char.isdigit():
                return "digit"
            if char.isalpha():
                return "ascii"
            return "symbol"

        # Use Unicode name for Japanese character classification
        try:
            name = unicodedata.name(char, "")
        except ValueError:
            return "symbol"

        if "CJK UNIFIED IDEOGRAPH" in name or "CJK COMPATIBILITY IDEOGRAPH" in name:
            return "kanji"
        if "HIRAGANA" in name:
            return "hiragana"
        if "KATAKANA" in name:
            return "katakana"
        if char.isdigit():
            return "digit"

        return "symbol"

    def _has_meta_discussion(self, text: str) -> bool:
        """Check if line contains meta-discussion markers."""
        return any(pattern.search(text) for pattern in _META_DISCUSSION_PATTERNS)

    def _is_inside_quotation_marks(self, text: str) -> bool:
        """Check if line content appears to be inside quotation marks.

        Returns True if the line contains paired quotation marks with content.
        """
        stripped = text.strip()

        for open_quote, close_quote in _QUOTATION_PAIRS:
            # Check if line starts with open and ends with close
            if stripped.startswith(open_quote) and stripped.endswith(close_quote):
                return True
            # Check if line contains a complete quoted segment
            if open_quote in stripped and close_quote in stripped:
                open_pos = stripped.find(open_quote)
                close_pos = stripped.rfind(close_quote)
                if open_pos < close_pos:
                    return True

        return False

    def _compute_context_features(
        self,
        idx: int,
        all_lines: tuple[AnnotatedLine, ...],
        all_flags: list[dict[str, bool]],
    ) -> dict[str, int]:
        """Compute contextual features from surrounding lines (window ±2)."""
        total = len(all_lines)

        # Define window bounds
        start_idx = max(0, idx - 2)
        end_idx = min(total, idx + 3)  # Exclusive

        # Aggregate counts
        greeting_count = 0
        closing_count = 0
        contact_count = 0
        blank_count = 0
        quote_count = 0
        separator_count = 0

        for i in range(start_idx, end_idx):
            if i == idx:
                continue  # Skip self

            flags = all_flags[i]
            line = all_lines[i]

            if flags["is_greeting"]:
                greeting_count += 1
            if flags["is_closing"]:
                closing_count += 1
            if flags["has_contact_info"]:
                contact_count += 1
            if flags["is_blank"]:
                blank_count += 1
            if line.quote_depth > 0:
                quote_count += 1
            if flags["is_visual_separator"] or line.is_delimiter:
                separator_count += 1

        return {
            "greeting_count": greeting_count,
            "closing_count": closing_count,
            "contact_count": contact_count,
            "blank_count": blank_count,
            "quote_count": quote_count,
            "separator_count": separator_count,
        }
