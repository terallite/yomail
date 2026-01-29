"""Type stubs for yomail - Extract body text from Japanese business emails."""

from pathlib import Path
from typing import Literal

# Exceptions
class ExtractionError(Exception):
    """Base exception for all extraction errors."""
    ...

class InvalidInputError(ExtractionError):
    """Input is not valid for processing."""
    message: str
    def __init__(self, message: str) -> None: ...
    def __str__(self) -> str: ...

class NoBodyDetectedError(ExtractionError):
    """No body content could be detected in the email."""
    message: str
    def __init__(self, message: str) -> None: ...
    def __str__(self) -> str: ...

class LowConfidenceError(ExtractionError):
    """Extraction confidence is below the threshold."""
    message: str
    confidence: float
    threshold: float
    def __init__(self, message: str, confidence: float, threshold: float) -> None: ...
    def __str__(self) -> str: ...

# Label type
Label = Literal["GREETING", "BODY", "CLOSING", "SIGNATURE", "QUOTE", "OTHER"]
LABELS: tuple[Label, ...]

# Data classes - Pipeline
class NormalizedEmail:
    """Result of normalizing an email."""
    lines: tuple[str, ...]
    text: str
    def __init__(self, lines: tuple[str, ...], text: str) -> None: ...

class AnnotatedLine:
    """A line with structural annotations."""
    text: str
    line_index: int
    quote_depth: int
    is_forward_reply_header: bool
    preceded_by_delimiter: bool
    is_delimiter: bool
    def __init__(
        self,
        text: str,
        line_index: int,
        quote_depth: int,
        is_forward_reply_header: bool,
        preceded_by_delimiter: bool,
        is_delimiter: bool,
    ) -> None: ...

class StructuralAnalysis:
    """Result of structural analysis on an email."""
    lines: tuple[AnnotatedLine, ...]
    has_quotes: bool
    has_forward_reply: bool
    first_quote_index: int | None
    last_quote_index: int | None
    def __init__(
        self,
        lines: tuple[AnnotatedLine, ...],
        has_quotes: bool,
        has_forward_reply: bool,
        first_quote_index: int | None,
        last_quote_index: int | None,
    ) -> None: ...

class LineFeatures:
    """Feature vector for a single line."""
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

class ExtractedFeatures:
    """Result of feature extraction for an entire email."""
    line_features: tuple[LineFeatures, ...]
    total_lines: int
    def __init__(
        self, line_features: tuple[LineFeatures, ...], total_lines: int
    ) -> None: ...

class LabeledLine:
    """A line with its predicted label and confidence."""
    text: str
    label: Label
    confidence: float
    label_probabilities: dict[Label, float]
    def __init__(
        self,
        text: str,
        label: Label,
        confidence: float,
        label_probabilities: dict[Label, float],
    ) -> None: ...

class SequenceLabelingResult:
    """Result of CRF sequence labeling."""
    labeled_lines: tuple[LabeledLine, ...]
    sequence_probability: float
    def __init__(
        self, labeled_lines: tuple[LabeledLine, ...], sequence_probability: float
    ) -> None: ...

class AssembledBody:
    """Result of body assembly."""
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

# Pipeline classes
class Normalizer:
    """Normalizes Japanese email text for downstream processing."""
    def normalize(self, text: str) -> NormalizedEmail: ...

class StructuralAnalyzer:
    """Analyzes email structure for quote detection and segmentation."""
    def analyze(self, filtered: FilteredContent) -> StructuralAnalysis: ...

class FeatureExtractor:
    """Extracts features from content-only email text."""
    def extract(
        self, analysis: StructuralAnalysis, filtered: FilteredContent
    ) -> ExtractedFeatures: ...

class CRFSequenceLabeler:
    """CRF-based sequence labeler for email line classification."""
    def __init__(
        self, model_path: Path | str | None = None, use_default: bool = True
    ) -> None: ...
    def load_model(self, model_path: Path | str) -> None: ...
    @property
    def is_loaded(self) -> bool: ...
    @property
    def labels(self) -> tuple[str, ...]: ...
    def predict(
        self, extracted: ExtractedFeatures, texts: tuple[str, ...]
    ) -> SequenceLabelingResult: ...

class CRFTrainer:
    """Trainer for CRF sequence labeling models."""
    def __init__(
        self,
        algorithm: str = "lbfgs",
        c1: float = 0.1,
        c2: float = 0.1,
        max_iterations: int = 100,
        all_possible_transitions: bool = True,
    ) -> None: ...
    def add_sequence(
        self,
        extracted: ExtractedFeatures,
        texts: tuple[str, ...],
        labels: tuple[Label, ...],
    ) -> None: ...
    def train(self, output_path: Path | str) -> None: ...
    def get_params(self) -> dict[str, str]: ...

class BodyAssembler:
    """Assembles the final body text from CRF-labeled lines."""
    def assemble(self, doc: ReconstructedDocument) -> AssembledBody: ...

# Additional types needed for FilteredContent and ReconstructedDocument
class ContentLine:
    """A non-blank line with whitespace context."""
    text: str
    original_index: int
    blank_lines_before: int
    blank_lines_after: int

class WhitespaceMap:
    """Mapping from content line indices to original line indices."""
    content_to_original: tuple[int, ...]
    blank_positions: frozenset[int]
    original_line_count: int

class FilteredContent:
    """Result of content filtering."""
    content_lines: tuple[ContentLine, ...]
    whitespace_map: WhitespaceMap
    original_lines: tuple[str, ...]

class ContentFilter:
    """Separates content lines from blank lines."""
    def filter(self, normalized: NormalizedEmail) -> FilteredContent: ...

class ReconstructedLine:
    """A line in the reconstructed document."""
    text: str
    original_index: int
    is_blank: bool
    label: Label | None
    confidence: float | None
    label_probabilities: dict[Label, float] | None

class ReconstructedDocument:
    """Full document with all lines restored and labeled."""
    lines: tuple[ReconstructedLine, ...]
    sequence_probability: float

class Reconstructor:
    """Reconstructs full document from content-only labels."""
    def reconstruct(
        self,
        labeling: SequenceLabelingResult,
        whitespace_map: WhitespaceMap,
        original_lines: tuple[str, ...],
    ) -> ReconstructedDocument: ...

# Main extractor result
class ExtractionResult:
    """Full extraction result with metadata."""
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

# Main extractor class
class EmailBodyExtractor:
    """Main class for extracting body text from Japanese emails."""
    def __init__(
        self,
        model_path: Path | str | None = None,
        confidence_threshold: float = 0.5,
    ) -> None: ...
    def load_model(self, model_path: Path | str) -> None: ...
    @property
    def is_model_loaded(self) -> bool: ...
    def extract(self, email_text: str) -> str: ...
    def extract_safe(self, email_text: str) -> str | None: ...
    def extract_with_metadata(self, email_text: str) -> ExtractionResult: ...

__version__: str
__all__: list[str]
