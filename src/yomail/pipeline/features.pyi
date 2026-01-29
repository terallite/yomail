"""Type stubs for yomail.pipeline.features."""

from yomail.pipeline.content_filter import FilteredContent
from yomail.pipeline.structural import StructuralAnalysis

class LineFeatures:
    """Feature vector for a single line.

    All numeric features are normalized to [0, 1] where applicable.
    Boolean features are stored as bool (converted to 0/1 for CRF).
    """
    # Positional features
    position_normalized: float
    position_reverse: float
    lines_from_start: int
    lines_from_end: int
    position_rel_first_quote: float
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
    # Whitespace context features
    blank_lines_before: int
    blank_lines_after: int
    # Structural features
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
    has_name_pattern: bool
    is_visual_separator: bool
    has_meta_discussion: bool
    is_inside_quotation_marks: bool
    # Contextual features
    context_greeting_count: int
    context_closing_count: int
    context_contact_count: int
    context_quote_count: int
    context_separator_count: int
    # Bracket features
    in_bracketed_section: bool
    bracket_has_signature_patterns: bool
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class ExtractedFeatures:
    """Result of feature extraction for an entire email.

    Attributes:
        line_features: Tuple of LineFeatures, one per line.
        total_lines: Total number of lines in the email.
    """
    line_features: tuple[LineFeatures, ...]
    total_lines: int
    def __init__(
        self, line_features: tuple[LineFeatures, ...], total_lines: int
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class FeatureExtractor:
    """Extracts features from content-only email text.

    Features are designed for CRF sequence labeling to classify
    each line as GREETING, BODY, CLOSING, SIGNATURE, QUOTE, or OTHER.
    Blank lines are filtered before feature extraction.
    """
    def extract(
        self, analysis: StructuralAnalysis, filtered: FilteredContent
    ) -> ExtractedFeatures:
        """Extract features from content-only structural analysis.

        Args:
            analysis: Output from StructuralAnalyzer.analyze_filtered().
            filtered: Output from ContentFilter (provides whitespace context).

        Returns:
            ExtractedFeatures with per-line feature vectors.
        """
        ...
