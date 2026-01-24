"""Tests for the CRF Sequence Labeler component (inference only)."""

import tempfile
from pathlib import Path

import pytest

from yomail.pipeline.crf import (
    LABELS,
    CRFSequenceLabeler,
    CRFTrainer,
    Label,
    LabeledLine,
    SequenceLabelingResult,
    _features_to_dict,
)
from yomail.pipeline.features import ExtractedFeatures, FeatureExtractor, LineFeatures
from yomail.pipeline.normalizer import Normalizer
from yomail.pipeline.structural import StructuralAnalyzer


def _make_line_features(
    position_normalized: float = 0.5,
    position_reverse: float = 0.5,
    lines_from_start: int = 5,
    lines_from_end: int = 5,
    position_rel_first_quote: float = 0.0,
    position_rel_last_quote: float = 0.0,
    line_length: int = 20,
    kanji_ratio: float = 0.3,
    hiragana_ratio: float = 0.3,
    katakana_ratio: float = 0.1,
    ascii_ratio: float = 0.2,
    digit_ratio: float = 0.05,
    symbol_ratio: float = 0.05,
    leading_whitespace: int = 0,
    trailing_whitespace: int = 0,
    is_blank: bool = False,
    quote_depth: int = 0,
    is_forward_reply_header: bool = False,
    preceded_by_delimiter: bool = False,
    is_delimiter: bool = False,
    is_greeting: bool = False,
    is_closing: bool = False,
    has_contact_info: bool = False,
    has_company_pattern: bool = False,
    has_position_pattern: bool = False,
    is_visual_separator: bool = False,
    has_meta_discussion: bool = False,
    is_inside_quotation_marks: bool = False,
    context_greeting_count: int = 0,
    context_closing_count: int = 0,
    context_contact_count: int = 0,
    context_blank_count: int = 0,
    context_quote_count: int = 0,
    context_separator_count: int = 0,
) -> LineFeatures:
    """Create a LineFeatures with sensible defaults."""
    return LineFeatures(
        position_normalized=position_normalized,
        position_reverse=position_reverse,
        lines_from_start=lines_from_start,
        lines_from_end=lines_from_end,
        position_rel_first_quote=position_rel_first_quote,
        position_rel_last_quote=position_rel_last_quote,
        line_length=line_length,
        kanji_ratio=kanji_ratio,
        hiragana_ratio=hiragana_ratio,
        katakana_ratio=katakana_ratio,
        ascii_ratio=ascii_ratio,
        digit_ratio=digit_ratio,
        symbol_ratio=symbol_ratio,
        leading_whitespace=leading_whitespace,
        trailing_whitespace=trailing_whitespace,
        is_blank=is_blank,
        quote_depth=quote_depth,
        is_forward_reply_header=is_forward_reply_header,
        preceded_by_delimiter=preceded_by_delimiter,
        is_delimiter=is_delimiter,
        is_greeting=is_greeting,
        is_closing=is_closing,
        has_contact_info=has_contact_info,
        has_company_pattern=has_company_pattern,
        has_position_pattern=has_position_pattern,
        is_visual_separator=is_visual_separator,
        has_meta_discussion=has_meta_discussion,
        is_inside_quotation_marks=is_inside_quotation_marks,
        context_greeting_count=context_greeting_count,
        context_closing_count=context_closing_count,
        context_contact_count=context_contact_count,
        context_blank_count=context_blank_count,
        context_quote_count=context_quote_count,
        context_separator_count=context_separator_count,
    )


def _extract_features(text: str) -> tuple[ExtractedFeatures, tuple[str, ...]]:
    """Run the full pipeline up to feature extraction."""
    normalizer = Normalizer()
    analyzer = StructuralAnalyzer()
    extractor = FeatureExtractor()

    normalized = normalizer.normalize(text)
    analysis = analyzer.analyze(normalized)
    features = extractor.extract(analysis)
    return features, normalized.lines


class TestFeatureConversion:
    """Tests for feature dictionary conversion."""

    def test_basic_conversion(self) -> None:
        """Features convert to dictionary."""
        features = _make_line_features()
        result = _features_to_dict(features, idx=5, total_lines=10)

        assert isinstance(result, dict)
        assert "pos_norm" in result
        assert "line_length" in result
        assert "is_greeting" in result

    def test_bos_eos_markers(self) -> None:
        """BOS/EOS markers are set for first/last lines."""
        features = _make_line_features()

        first = _features_to_dict(features, idx=0, total_lines=3)
        middle = _features_to_dict(features, idx=1, total_lines=3)
        last = _features_to_dict(features, idx=2, total_lines=3)

        assert first.get("BOS") is True
        assert "EOS" not in first

        assert "BOS" not in middle
        assert "EOS" not in middle

        assert "BOS" not in last
        assert last.get("EOS") is True

    def test_single_line_has_both_markers(self) -> None:
        """Single line has both BOS and EOS."""
        features = _make_line_features()
        result = _features_to_dict(features, idx=0, total_lines=1)

        assert result.get("BOS") is True
        assert result.get("EOS") is True

    def test_position_buckets(self) -> None:
        """Position buckets are categorical."""
        start = _make_line_features(position_normalized=0.05)
        end = _make_line_features(position_normalized=0.95)

        start_dict = _features_to_dict(start, idx=0, total_lines=10)
        end_dict = _features_to_dict(end, idx=9, total_lines=10)

        assert start_dict["pos_bucket"] == "start"
        assert end_dict["pos_bucket"] == "end"

    def test_quote_depth_categorical(self) -> None:
        """Quote depth is categorized."""
        unquoted = _make_line_features(quote_depth=0)
        quoted = _make_line_features(quote_depth=2)

        unquoted_dict = _features_to_dict(unquoted, idx=0, total_lines=1)
        quoted_dict = _features_to_dict(quoted, idx=0, total_lines=1)

        assert unquoted_dict["quote_depth_cat"] == "unquoted"
        assert quoted_dict["quote_depth_cat"] == "quoted"

    def test_char_type_categorical(self) -> None:
        """Character composition is categorized."""
        blank = _make_line_features(is_blank=True)
        ascii_heavy = _make_line_features(ascii_ratio=0.9, kanji_ratio=0.0, hiragana_ratio=0.0)
        japanese = _make_line_features(kanji_ratio=0.5, hiragana_ratio=0.3, ascii_ratio=0.1)

        assert _features_to_dict(blank, 0, 1)["char_type"] == "blank"
        assert _features_to_dict(ascii_heavy, 0, 1)["char_type"] == "ascii_heavy"
        assert _features_to_dict(japanese, 0, 1)["char_type"] == "japanese_heavy"


class TestCRFSequenceLabeler:
    """Tests for CRF sequence labeler."""

    def test_not_loaded_raises(self) -> None:
        """Predict raises if no model loaded."""
        labeler = CRFSequenceLabeler()
        features = ExtractedFeatures(line_features=(), total_lines=0)

        with pytest.raises(RuntimeError, match="No CRF model loaded"):
            labeler.predict(features, ())

    def test_is_loaded_property(self) -> None:
        """is_loaded reflects model state."""
        labeler = CRFSequenceLabeler()
        assert labeler.is_loaded is False

    def test_missing_model_file_raises(self) -> None:
        """Loading missing file raises FileNotFoundError."""
        labeler = CRFSequenceLabeler()

        with pytest.raises(FileNotFoundError):
            labeler.load_model("/nonexistent/model.crfsuite")

    def test_empty_input_returns_empty(self) -> None:
        """Empty input returns empty result."""
        # Create a minimal model to test with
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_minimal_model(model_path)

            labeler = CRFSequenceLabeler(model_path)
            features = ExtractedFeatures(line_features=(), total_lines=0)
            result = labeler.predict(features, ())

            assert result.labeled_lines == ()
            assert result.sequence_probability == 1.0

    def test_labels_property_default(self) -> None:
        """Labels property returns expected labels when no model loaded."""
        labeler = CRFSequenceLabeler()
        assert labeler.labels == LABELS


class TestIntegrationWithModel:
    """Integration tests with a trained model."""

    def test_predict_returns_labeled_lines(self) -> None:
        """Prediction returns LabeledLine objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_minimal_model(model_path)

            labeler = CRFSequenceLabeler(model_path)

            text = "お世話になっております。\n本日の件についてご連絡いたします。\nよろしくお願いいたします。"
            features, texts = _extract_features(text)
            result = labeler.predict(features, texts)

            assert isinstance(result, SequenceLabelingResult)
            assert len(result.labeled_lines) == 3

            for line in result.labeled_lines:
                assert isinstance(line, LabeledLine)
                assert line.label in LABELS
                assert 0.0 <= line.confidence <= 1.0
                assert isinstance(line.label_probabilities, dict)

    def test_predict_sequence_probability(self) -> None:
        """Sequence probability is between 0 and 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_minimal_model(model_path)

            labeler = CRFSequenceLabeler(model_path)

            text = "テスト\nメール"
            features, texts = _extract_features(text)
            result = labeler.predict(features, texts)

            assert 0.0 <= result.sequence_probability <= 1.0

    def test_label_probabilities_sum_roughly_to_one(self) -> None:
        """Label probabilities for each position sum to approximately 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_minimal_model(model_path)

            labeler = CRFSequenceLabeler(model_path)

            text = "お世話になっております。"
            features, texts = _extract_features(text)
            result = labeler.predict(features, texts)

            for line in result.labeled_lines:
                total_prob = sum(line.label_probabilities.values())
                # Allow some floating point tolerance
                assert 0.99 <= total_prob <= 1.01


def _train_minimal_model(model_path: Path) -> None:
    """Train a minimal model for testing.

    Creates a simple model trained on a few examples covering all labels.
    This is intentionally minimal - just enough to test the inference code.
    """
    trainer = CRFTrainer(max_iterations=50)

    # Training examples covering different label types
    examples: list[tuple[str, tuple[Label, ...]]] = [
        # Greeting + Body + Closing
        (
            "お世話になっております。\n本日は会議の件でご連絡いたします。\nよろしくお願いいたします。",
            ("GREETING", "BODY", "CLOSING"),
        ),
        # Body only
        (
            "明日の予定を確認しました。\n問題ありません。",
            ("BODY", "BODY"),
        ),
        # With signature
        (
            "ご確認ください。\n---\n田中太郎\nTEL: 03-1234-5678",
            ("BODY", "SEPARATOR", "SIGNATURE", "SIGNATURE"),
        ),
        # With quote
        (
            "> 前回のメール\n承知しました。",
            ("QUOTE", "BODY"),
        ),
        # Separator and Other
        (
            "情報です。\n\n以上",
            ("BODY", "SEPARATOR", "OTHER"),
        ),
    ]

    for text, labels in examples:
        features, texts = _extract_features(text)
        trainer.add_sequence(features, texts, labels)

    trainer.train(model_path)
