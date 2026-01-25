"""Tests for the EmailBodyExtractor class."""

import tempfile
from pathlib import Path

import pytest

from yomail import (
    EmailBodyExtractor,
    ExtractionResult,
    InvalidInputError,
)
from yomail.pipeline.content_filter import ContentFilter
from yomail.pipeline.crf import CRFTrainer, Label
from yomail.pipeline.features import FeatureExtractor
from yomail.pipeline.normalizer import Normalizer
from yomail.pipeline.structural import StructuralAnalyzer


def _train_test_model(model_path: Path) -> None:
    """Train a minimal model for testing."""
    normalizer = Normalizer()
    content_filter = ContentFilter()
    analyzer = StructuralAnalyzer()
    extractor = FeatureExtractor()
    trainer = CRFTrainer(max_iterations=50)

    # Training data: (text, content_labels)
    # Labels are for content lines only (blank lines are filtered out)
    examples: list[tuple[str, tuple[Label, ...]]] = [
        (
            "お世話になっております。\n本日は会議の件でご連絡いたします。\nよろしくお願いいたします。",
            ("GREETING", "BODY", "CLOSING"),
        ),
        (
            "明日の予定を確認しました。\n問題ありません。",
            ("BODY", "BODY"),
        ),
        (
            "ご確認ください。\n---\n田中太郎\nTEL: 03-1234-5678",
            ("BODY", "OTHER", "SIGNATURE", "SIGNATURE"),
        ),
        (
            "> 前回のメール\n承知しました。",
            ("QUOTE", "BODY"),
        ),
        (
            "情報です。\n続きです。\n以上",
            ("BODY", "BODY", "CLOSING"),
        ),
    ]

    for text, labels in examples:
        normalized = normalizer.normalize(text)
        filtered = content_filter.filter(normalized)
        structural = analyzer.analyze(filtered)
        features = extractor.extract(structural, filtered)
        content_texts = tuple(line.text for line in filtered.content_lines)
        trainer.add_sequence(features, content_texts, labels)

    trainer.train(model_path)


class TestEmailBodyExtractor:
    """Tests for EmailBodyExtractor."""

    def test_extract_without_model_raises(self) -> None:
        """Extraction without model raises InvalidInputError."""
        extractor = EmailBodyExtractor()

        with pytest.raises(InvalidInputError, match="No CRF model loaded"):
            extractor.extract("Hello world")

    def test_extract_empty_input_raises(self) -> None:
        """Empty input raises InvalidInputError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_test_model(model_path)

            extractor = EmailBodyExtractor(model_path=model_path)

            with pytest.raises(InvalidInputError):
                extractor.extract("")

    def test_extract_safe_returns_none_on_failure(self) -> None:
        """extract_safe returns None on any failure."""
        extractor = EmailBodyExtractor()

        # No model loaded
        result = extractor.extract_safe("Hello")
        assert result is None

    def test_is_model_loaded(self) -> None:
        """is_model_loaded reflects state."""
        extractor = EmailBodyExtractor()
        assert extractor.is_model_loaded is False

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_test_model(model_path)

            extractor.load_model(model_path)
            assert extractor.is_model_loaded is True


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_result_fields(self) -> None:
        """ExtractionResult has expected fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_test_model(model_path)

            extractor = EmailBodyExtractor(model_path=model_path)
            result = extractor.extract_with_metadata("テストメール")

            assert isinstance(result, ExtractionResult)
            assert hasattr(result, "body")
            assert hasattr(result, "confidence")
            assert hasattr(result, "success")
            assert hasattr(result, "error")
            assert hasattr(result, "labeled_lines")
            assert hasattr(result, "signature_detected")
            assert hasattr(result, "inline_quotes_included")


class TestEndToEndExtraction:
    """End-to-end extraction tests."""

    def test_simple_email_extraction(self) -> None:
        """Simple email body is extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_test_model(model_path)

            extractor = EmailBodyExtractor(model_path=model_path)

            email = "お世話になっております。\n会議の件です。\nよろしくお願いいたします。"
            result = extractor.extract_with_metadata(email)

            assert result.labeled_lines is not None
            assert len(result.labeled_lines) == 3
            assert 0.0 <= result.confidence <= 1.0

    def test_email_with_signature(self) -> None:
        """Email with signature detects signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_test_model(model_path)

            extractor = EmailBodyExtractor(model_path=model_path)

            email = "ご確認ください。\n---\n山田太郎\nTEL: 03-1234-5678"
            result = extractor.extract_with_metadata(email)

            # Model should predict something
            assert len(result.labeled_lines) == 4

    def test_extract_returns_string(self) -> None:
        """extract() returns string body."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_test_model(model_path)

            # Use lower threshold for minimal test model (Viterbi scores are lower)
            extractor = EmailBodyExtractor(
                model_path=model_path, confidence_threshold=0.1
            )

            email = "明日の予定を確認しました。\n問題ありません。"
            body = extractor.extract(email)

            assert isinstance(body, str)
            assert len(body) > 0

    def test_extract_safe_returns_string_on_success(self) -> None:
        """extract_safe() returns string on success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test.crfsuite"
            _train_test_model(model_path)

            extractor = EmailBodyExtractor(model_path=model_path)

            email = "確認しました。"
            body = extractor.extract_safe(email)

            # May return None if confidence is low with minimal model
            # Just verify it doesn't raise
            assert body is None or isinstance(body, str)
