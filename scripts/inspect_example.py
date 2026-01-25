#!/usr/bin/env python
"""Inspect a specific example from the test set, showing features and predictions.

Usage:
    python scripts/inspect_example.py 1871                      # Show all lines
    python scripts/inspect_example.py 1871 --line 9             # Show details for line 9
    python scripts/inspect_example.py 1871 --search "よろしく"  # Find and show line
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from yomail.pipeline.content_filter import ContentFilter
from yomail.pipeline.crf import CRFSequenceLabeler, _extract_feature_sequence
from yomail.pipeline.features import ExtractedFeatures, FeatureExtractor, LineFeatures
from yomail.pipeline.normalizer import Normalizer
from yomail.pipeline.structural import StructuralAnalyzer

MODEL_PATH = Path("models/email_body.crfsuite")


def load_example(path: Path, index: int) -> dict:
    """Load example at index from JSONL file."""
    with open(path) as f:
        for i, line in enumerate(f):
            if i == index:
                return json.loads(line)
    raise ValueError(f"Index {index} not found")


def run_pipeline(email_text: str) -> tuple[
    list[str],  # predicted labels (content lines only)
    list[float],  # marginals
    ExtractedFeatures,
    list[str],  # content line texts
]:
    """Run the full pipeline and return predictions with features."""
    normalizer = Normalizer()
    content_filter = ContentFilter()
    structural_analyzer = StructuralAnalyzer()
    feature_extractor = FeatureExtractor()
    labeler = CRFSequenceLabeler()
    labeler.load_model(MODEL_PATH)

    normalized = normalizer.normalize(email_text)
    filtered = content_filter.filter(normalized)
    structural = structural_analyzer.analyze(filtered)
    extracted = feature_extractor.extract(structural, filtered)

    content_texts = tuple(cl.text for cl in filtered.content_lines)
    labeling = labeler.predict(extracted, content_texts)

    # Get marginals by re-setting the tagger
    crf_features = _extract_feature_sequence(extracted, content_texts)
    labeler._tagger.set(crf_features)

    predicted_labels = [ll.label for ll in labeling.labeled_lines]
    marginals = [
        labeler._tagger.marginal(label, i)
        for i, label in enumerate(predicted_labels)
    ]

    return predicted_labels, marginals, extracted, list(content_texts)


def print_line_table(
    ground_truth: list[dict],
    predicted_labels: list[str],
    marginals: list[float],
    content_texts: list[str],
    highlight_idx: int | None = None,
) -> None:
    """Print comparison table of predictions vs ground truth.

    Ground truth includes blank lines; predictions are content-only.
    We align by counting content lines.
    """
    print("LABELS (Predicted vs Ground Truth):")
    print(f"  {'Pred':<10} {'Conf':>5}  {'Truth':<10}  Text")
    print(f"  {'-'*10} {'-'*5}  {'-'*10}  {'-'*55}")

    content_idx = 0
    for gt in ground_truth:
        text = gt["text"]
        truth_label = gt["label"]
        text_preview = text[:55] + "..." if len(text) > 55 else text

        if text.strip():  # Content line
            if content_idx < len(predicted_labels):
                pred_label = predicted_labels[content_idx]
                conf = marginals[content_idx]
                match = pred_label == truth_label
                marker = "  " if match else "* "
                highlight = ">>>" if content_idx == highlight_idx else "   "
                print(f"{highlight}{marker}{pred_label:<10} {conf:>5.2f}  {truth_label:<10}  {text_preview}")
            else:
                print(f"      {'???':<10} {'???':>5}  {truth_label:<10}  {text_preview}")
            content_idx += 1
        else:
            # Blank line - no prediction
            print(f"      {'--':<10} {'--':>5}  {truth_label:<10}  (blank)")


def print_features(lf: LineFeatures, text: str, truth: str, pred: str, conf: float) -> None:
    """Print detailed features for a line."""
    print(f"Text: {text}")
    print(f"Ground truth: {truth}")
    print(f"Predicted: {pred} (conf: {conf:.3f})")
    print()

    print("Positional:")
    print(f"  position_normalized: {lf.position_normalized:.3f}")
    print(f"  position_reverse: {lf.position_reverse:.3f}")
    print(f"  lines_from_start: {lf.lines_from_start}")
    print(f"  lines_from_end: {lf.lines_from_end}")
    print()

    print("Content:")
    print(f"  line_length: {lf.line_length}")
    print(f"  kanji_ratio: {lf.kanji_ratio:.3f}")
    print(f"  hiragana_ratio: {lf.hiragana_ratio:.3f}")
    print(f"  katakana_ratio: {lf.katakana_ratio:.3f}")
    print(f"  ascii_ratio: {lf.ascii_ratio:.3f}")
    print(f"  digit_ratio: {lf.digit_ratio:.3f}")
    print(f"  symbol_ratio: {lf.symbol_ratio:.3f}")
    print()

    print("Whitespace context:")
    print(f"  blank_lines_before: {lf.blank_lines_before}")
    print(f"  blank_lines_after: {lf.blank_lines_after}")
    print()

    print("Structural:")
    print(f"  quote_depth: {lf.quote_depth}")
    print(f"  is_forward_reply_header: {lf.is_forward_reply_header}")
    print(f"  preceded_by_delimiter: {lf.preceded_by_delimiter}")
    print(f"  is_delimiter: {lf.is_delimiter}")
    print()

    print("Pattern flags:")
    print(f"  is_greeting: {lf.is_greeting}")
    print(f"  is_closing: {lf.is_closing}")
    print(f"  has_contact_info: {lf.has_contact_info}")
    print(f"  has_company_pattern: {lf.has_company_pattern}")
    print(f"  has_position_pattern: {lf.has_position_pattern}")
    print(f"  has_name_pattern: {lf.has_name_pattern}")
    print(f"  is_visual_separator: {lf.is_visual_separator}")
    print(f"  has_meta_discussion: {lf.has_meta_discussion}")
    print(f"  is_inside_quotation_marks: {lf.is_inside_quotation_marks}")
    print()

    print("Bracket features:")
    print(f"  in_bracketed_section: {lf.in_bracketed_section}")
    print(f"  bracket_has_signature_patterns: {lf.bracket_has_signature_patterns}")
    print()

    print("Contextual (window ±2):")
    print(f"  context_greeting_count: {lf.context_greeting_count}")
    print(f"  context_closing_count: {lf.context_closing_count}")
    print(f"  context_contact_count: {lf.context_contact_count}")
    print(f"  context_quote_count: {lf.context_quote_count}")
    print(f"  context_separator_count: {lf.context_separator_count}")


def print_marginals(labeler: CRFSequenceLabeler, idx: int) -> None:
    """Print all label marginals for a position."""
    print()
    print("Label marginals:")
    # Only include labels that exist in the model (OTHER is not trained)
    for label in labeler._tagger.labels():
        prob = labeler._tagger.marginal(label, idx)
        print(f"  {label:<12}: {prob:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=int, help="Example index in test set")
    parser.add_argument("--test-file", type=Path, default=Path("data/test.jsonl"))
    parser.add_argument("--line", type=int, help="Content line index to inspect")
    parser.add_argument("--search", type=str, help="Search for text in content lines")
    args = parser.parse_args()

    # Load example
    example = load_example(args.test_file, args.index)
    email_text = example["email_text"]
    ground_truth = example["lines"]
    metadata = example.get("metadata", {})

    print(f"Example #{args.index}")
    print(f"Template: {metadata.get('template_type', 'unknown')}")
    print("=" * 80)
    print()

    # Run pipeline
    predicted_labels, marginals, extracted, content_texts = run_pipeline(email_text)

    # Find target line if --search specified
    target_idx = args.line
    if args.search:
        for i, text in enumerate(content_texts):
            if args.search in text:
                target_idx = i
                print(f"Found '{args.search}' at content line {i}")
                print()
                break
        else:
            print(f"'{args.search}' not found in any content line")
            return

    # Print table
    print_line_table(ground_truth, predicted_labels, marginals, content_texts, target_idx)

    # Print detailed features if target specified
    if target_idx is not None:
        if target_idx >= len(extracted.line_features):
            print(f"\nError: Line {target_idx} out of range (max {len(extracted.line_features) - 1})")
            return

        print()
        print("=" * 80)
        print(f"DETAILED FEATURES FOR CONTENT LINE {target_idx}")
        print("=" * 80)
        print()

        lf = extracted.line_features[target_idx]
        text = content_texts[target_idx]
        pred = predicted_labels[target_idx]
        conf = marginals[target_idx]

        # Find ground truth label for this content line
        # Ground truth includes blank lines, so we count content lines to find the match
        truth = "?"
        content_count = 0
        for gt in ground_truth:
            if gt["text"].strip():  # Non-blank
                if content_count == target_idx:
                    truth = gt["label"]
                    break
                content_count += 1

        print_features(lf, text, truth, pred, conf)

        # Also print marginals
        labeler = CRFSequenceLabeler()
        labeler.load_model(MODEL_PATH)
        crf_features = _extract_feature_sequence(extracted, tuple(content_texts))
        labeler._tagger.set(crf_features)
        print_marginals(labeler, target_idx)


if __name__ == "__main__":
    main()
