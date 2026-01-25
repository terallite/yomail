"""CRF Sequence Labeler for Japanese email line classification.

Uses python-crfsuite to predict labels for each line of an email:
- GREETING: Opening formulas
- BODY: Substantive content
- CLOSING: Closing formulas
- SIGNATURE: Signature block lines
- QUOTE: Quoted content
- SEPARATOR: Visual dividers, blank lines
- OTHER: Headers, noise, unclassifiable
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pycrfsuite

from yomail.pipeline.features import ExtractedFeatures, LineFeatures

logger = logging.getLogger(__name__)


# Label definitions matching DESIGN.md
Label = Literal["GREETING", "BODY", "CLOSING", "SIGNATURE", "QUOTE", "SEPARATOR", "OTHER"]

LABELS: tuple[Label, ...] = ("GREETING", "BODY", "CLOSING", "SIGNATURE", "QUOTE", "SEPARATOR", "OTHER")


@dataclass(frozen=True, slots=True)
class LabeledLine:
    """A line with its predicted label and confidence.

    Attributes:
        text: Original line text.
        label: Predicted label (one of LABELS).
        confidence: Marginal probability for the predicted label (0.0 to 1.0).
        label_probabilities: Marginal probabilities for all labels.
    """

    text: str
    label: Label
    confidence: float
    label_probabilities: dict[Label, float]


@dataclass(frozen=True, slots=True)
class SequenceLabelingResult:
    """Result of CRF sequence labeling.

    Attributes:
        labeled_lines: Tuple of LabeledLine objects, one per input line.
        sequence_probability: Probability of the entire predicted label sequence.
    """

    labeled_lines: tuple[LabeledLine, ...]
    sequence_probability: float


def _features_to_dict(features: LineFeatures, idx: int, total_lines: int) -> dict[str, str | float | bool]:
    """Convert LineFeatures to a feature dictionary for CRFsuite.

    CRFsuite accepts features as dict[str, value] where value can be:
    - str for categorical features
    - float for numeric features
    - bool for boolean features

    Args:
        features: LineFeatures for a single line.
        idx: Line index (for BOS/EOS markers).
        total_lines: Total number of lines.

    Returns:
        Feature dictionary for CRFsuite.
    """
    feat: dict[str, str | float | bool] = {}

    # Special markers for beginning/end of sequence
    if idx == 0:
        feat["BOS"] = True
    if idx == total_lines - 1:
        feat["EOS"] = True

    # Positional features (numeric)
    feat["pos_norm"] = features.position_normalized
    feat["pos_rev"] = features.position_reverse
    feat["lines_from_start"] = float(features.lines_from_start)
    feat["lines_from_end"] = float(features.lines_from_end)
    feat["pos_rel_first_quote"] = features.position_rel_first_quote
    feat["pos_rel_last_quote"] = features.position_rel_last_quote

    # Content features (numeric)
    feat["line_length"] = float(features.line_length)
    feat["kanji_ratio"] = features.kanji_ratio
    feat["hiragana_ratio"] = features.hiragana_ratio
    feat["katakana_ratio"] = features.katakana_ratio
    feat["ascii_ratio"] = features.ascii_ratio
    feat["digit_ratio"] = features.digit_ratio
    feat["symbol_ratio"] = features.symbol_ratio
    feat["leading_ws"] = float(features.leading_whitespace)
    feat["trailing_ws"] = float(features.trailing_whitespace)

    # Whitespace context features
    feat["blank_lines_before"] = float(features.blank_lines_before)
    feat["blank_lines_after"] = float(features.blank_lines_after)

    # Structural features
    feat["quote_depth"] = float(features.quote_depth)
    feat["is_forward_reply_header"] = features.is_forward_reply_header
    feat["preceded_by_delimiter"] = features.preceded_by_delimiter
    feat["is_delimiter"] = features.is_delimiter

    # Pattern flags (boolean)
    feat["is_greeting"] = features.is_greeting
    feat["is_closing"] = features.is_closing
    feat["has_contact_info"] = features.has_contact_info
    feat["has_company_pattern"] = features.has_company_pattern
    feat["has_position_pattern"] = features.has_position_pattern
    feat["has_name_pattern"] = features.has_name_pattern
    feat["is_visual_separator"] = features.is_visual_separator
    feat["has_meta_discussion"] = features.has_meta_discussion
    feat["is_inside_quotation_marks"] = features.is_inside_quotation_marks

    # Contextual features (numeric)
    feat["ctx_greeting_count"] = float(features.context_greeting_count)
    feat["ctx_closing_count"] = float(features.context_closing_count)
    feat["ctx_contact_count"] = float(features.context_contact_count)
    feat["ctx_quote_count"] = float(features.context_quote_count)
    feat["ctx_separator_count"] = float(features.context_separator_count)

    # Derived categorical features for stronger signal
    if features.quote_depth > 0:
        feat["quote_depth_cat"] = "quoted"
    else:
        feat["quote_depth_cat"] = "unquoted"

    # Position buckets for categorical features
    if features.position_normalized < 0.1:
        feat["pos_bucket"] = "start"
    elif features.position_normalized < 0.3:
        feat["pos_bucket"] = "early"
    elif features.position_normalized < 0.7:
        feat["pos_bucket"] = "middle"
    elif features.position_normalized < 0.9:
        feat["pos_bucket"] = "late"
    else:
        feat["pos_bucket"] = "end"

    # Character composition bucket (content lines only, no blank option)
    if features.ascii_ratio > 0.8:
        feat["char_type"] = "ascii_heavy"
    elif features.kanji_ratio + features.hiragana_ratio > 0.7:
        feat["char_type"] = "japanese_heavy"
    else:
        feat["char_type"] = "mixed"

    return feat


def _extract_feature_sequence(
    extracted: ExtractedFeatures,
    texts: tuple[str, ...],
) -> list[dict[str, str | float | bool]]:
    """Extract feature sequence for all lines.

    Args:
        extracted: ExtractedFeatures from the FeatureExtractor.
        texts: Original text lines (for reference, not used in features).

    Returns:
        List of feature dictionaries, one per line.
    """
    total_lines = extracted.total_lines
    return [
        _features_to_dict(line_features, idx, total_lines)
        for idx, line_features in enumerate(extracted.line_features)
    ]


class CRFSequenceLabeler:
    """CRF-based sequence labeler for email line classification.

    Uses python-crfsuite for fast, lightweight CRF inference.
    Supports loading pre-trained models and making predictions
    with per-label marginal probabilities.
    """

    def __init__(self, model_path: Path | str | None = None) -> None:
        """Initialize the CRF labeler.

        Args:
            model_path: Path to a trained CRF model file.
                If None, the labeler must be loaded later with load_model().
        """
        self._tagger: pycrfsuite.Tagger | None = None
        self._model_path: Path | None = None

        if model_path is not None:
            self.load_model(model_path)

    def load_model(self, model_path: Path | str) -> None:
        """Load a trained CRF model.

        Args:
            model_path: Path to the model file.

        Raises:
            FileNotFoundError: If the model file does not exist.
            RuntimeError: If the model cannot be loaded.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        self._tagger = pycrfsuite.Tagger()
        try:
            self._tagger.open(str(path))
        except Exception as exc:
            self._tagger = None
            raise RuntimeError(f"Failed to load CRF model: {exc}") from exc

        self._model_path = path
        logger.info("Loaded CRF model from %s", path)

    @property
    def is_loaded(self) -> bool:
        """Whether a model is currently loaded."""
        return self._tagger is not None

    @property
    def labels(self) -> tuple[str, ...]:
        """Get the labels known by the loaded model."""
        if self._tagger is None:
            return LABELS
        return tuple(self._tagger.labels())

    def predict(
        self,
        extracted: ExtractedFeatures,
        texts: tuple[str, ...],
    ) -> SequenceLabelingResult:
        """Predict labels for email lines.

        Args:
            extracted: Feature extraction result from FeatureExtractor.
            texts: Original text lines corresponding to the features.

        Returns:
            SequenceLabelingResult with labeled lines and probabilities.

        Raises:
            RuntimeError: If no model is loaded.
        """
        if self._tagger is None:
            raise RuntimeError("No CRF model loaded. Call load_model() first.")

        if extracted.total_lines == 0:
            return SequenceLabelingResult(
                labeled_lines=(),
                sequence_probability=1.0,
            )

        # Extract features
        feature_seq = _extract_feature_sequence(extracted, texts)

        # Set the sequence for tagging
        self._tagger.set(feature_seq)

        # Get predicted labels
        predicted_labels = self._tagger.tag()

        # Get sequence probability (probability of the predicted sequence)
        sequence_prob = self._tagger.probability(predicted_labels)

        # Get marginal probabilities for each position
        model_labels = self._tagger.labels()
        labeled_lines: list[LabeledLine] = []

        for idx, (text, pred_label) in enumerate(zip(texts, predicted_labels, strict=True)):
            # Compute marginal probability for each label at this position
            label_probs: dict[Label, float] = {}
            for label in LABELS:
                if label in model_labels:
                    label_probs[label] = self._tagger.marginal(label, idx)
                else:
                    label_probs[label] = 0.0

            # Confidence is the marginal probability of the predicted label
            confidence = label_probs.get(pred_label, 0.0)

            # Validate label is one of the expected labels
            validated_label: Label
            if pred_label in LABELS:
                validated_label = pred_label
            else:
                logger.warning("Unknown label '%s' at position %d, defaulting to OTHER", pred_label, idx)
                validated_label = "OTHER"
                confidence = 0.0

            labeled_lines.append(
                LabeledLine(
                    text=text,
                    label=validated_label,
                    confidence=confidence,
                    label_probabilities=label_probs,
                )
            )

        return SequenceLabelingResult(
            labeled_lines=tuple(labeled_lines),
            sequence_probability=sequence_prob,
        )


class CRFTrainer:
    """Trainer for CRF sequence labeling models.

    Wraps python-crfsuite's Trainer with a convenient interface
    for training on labeled email data.
    """

    def __init__(
        self,
        algorithm: str = "lbfgs",
        c1: float = 0.1,
        c2: float = 0.1,
        max_iterations: int = 100,
        all_possible_transitions: bool = True,
    ) -> None:
        """Initialize the CRF trainer.

        Args:
            algorithm: Training algorithm. Options: 'lbfgs', 'l2sgd', 'ap', 'pa', 'arow'.
            c1: L1 regularization coefficient.
            c2: L2 regularization coefficient.
            max_iterations: Maximum number of training iterations.
            all_possible_transitions: Include transitions not in training data.
        """
        self._trainer = pycrfsuite.Trainer(verbose=False)
        self._trainer.set_params(
            {
                "c1": c1,
                "c2": c2,
                "max_iterations": max_iterations,
                "feature.possible_transitions": all_possible_transitions,
            }
        )
        self._trainer.select(algorithm)

    def add_sequence(
        self,
        extracted: ExtractedFeatures,
        texts: tuple[str, ...],
        labels: tuple[Label, ...],
    ) -> None:
        """Add a training sequence.

        Args:
            extracted: Feature extraction result from FeatureExtractor.
            texts: Original text lines.
            labels: Ground truth labels for each line.

        Raises:
            ValueError: If the number of labels doesn't match the number of lines.
        """
        if len(labels) != extracted.total_lines:
            raise ValueError(
                f"Number of labels ({len(labels)}) doesn't match "
                f"number of lines ({extracted.total_lines})"
            )

        if len(texts) != extracted.total_lines:
            raise ValueError(
                f"Number of texts ({len(texts)}) doesn't match "
                f"number of lines ({extracted.total_lines})"
            )

        feature_seq = _extract_feature_sequence(extracted, texts)
        self._trainer.append(feature_seq, list(labels))

    def train(self, output_path: Path | str) -> None:
        """Train the model and save to file.

        Args:
            output_path: Path to save the trained model.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Training CRF model...")
        self._trainer.train(str(path))
        logger.info("Saved CRF model to %s", path)

    def get_params(self) -> dict[str, str]:
        """Get current training parameters."""
        return dict(self._trainer.params())
