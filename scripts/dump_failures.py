#!/usr/bin/env python3
"""Dump confident failure examples to a text file for analysis.

Shows side-by-side comparison of predicted vs ground truth labels.

Usage:
    python scripts/dump_failures.py data/test.jsonl
    python scripts/dump_failures.py data/test.jsonl -o failures.txt
    python scripts/dump_failures.py data/test.jsonl -n 50
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from yomail import EmailBodyExtractor
from yomail.exceptions import ExtractionError
from yomail.pipeline.normalizer import Normalizer

_normalizer = Normalizer()


def normalize_text(text: str | None) -> str:
    """Normalize text for comparison (strip lines, remove empty)."""
    if text is None:
        return ""
    lines = text.strip().split("\n")
    lines = [line.strip() for line in lines]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def get_expected_body(lines_data: list[dict]) -> str:
    """Compute expected body same way as evaluate.py - with normalization."""
    # First normalize all lines
    normalized_lines = []
    for item in lines_data:
        text = item["text"]
        if not text or not text.strip():
            normalized_lines.append({"text": "", "label": item["label"]})
        else:
            try:
                normalized = _normalizer.normalize(text)
                normalized_text = "\n".join(normalized.lines) if normalized.lines else ""
                normalized_lines.append({"text": normalized_text, "label": item["label"]})
            except Exception:
                normalized_lines.append({"text": text, "label": item["label"]})
    lines_data = normalized_lines

    content_labels = {"GREETING", "BODY", "CLOSING"}
    content_indices = [
        i
        for i, line in enumerate(lines_data)
        if line["label"] in content_labels
    ]
    if len(content_indices) < 2:
        first_content = content_indices[0] if content_indices else -1
        last_content = content_indices[-1] if content_indices else -1
    else:
        first_content = content_indices[0]
        last_content = content_indices[-1]

    # Find signature boundary
    signature_index = None
    for idx, item in enumerate(lines_data):
        if item["label"] == "SIGNATURE":
            signature_index = idx
            break
    end_index = signature_index if signature_index is not None else len(lines_data)

    # Build content blocks
    blocks: list[list[str]] = []
    current_block: list[str] = []
    separator_buffer: list[str] = []

    for idx in range(end_index):
        item = lines_data[idx]
        label = item["label"]
        text = item["text"]

        if label in content_labels:
            current_block.extend(separator_buffer)
            separator_buffer = []
            current_block.append(text)
        elif label == "OTHER":
            separator_buffer.append(text)
        elif label == "QUOTE":
            if first_content < idx < last_content:
                current_block.extend(separator_buffer)
                separator_buffer = []
                current_block.append(text)
            else:
                if current_block:
                    blocks.append(current_block)
                    current_block = []
                separator_buffer = []

    if current_block:
        blocks.append(current_block)

    # Select body
    if signature_index is not None:
        selected_lines: list[str] = []
        for block in blocks:
            selected_lines.extend(block)
    else:
        selected_lines = max(blocks, key=len) if blocks else []

    return "\n".join(selected_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Dump confident failure examples for analysis"
    )
    parser.add_argument(
        "test_data",
        type=Path,
        help="Path to JSONL test data file",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=Path,
        default=Path("models/email_body.crfsuite"),
        help="Model path (default: models/email_body.crfsuite)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("tmp/confident_failures.txt"),
        help="Output file path (default: tmp/confident_failures.txt)",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=20,
        help="Number of examples to output (default: 20)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.test_data.exists():
        print(f"Error: Test data file not found: {args.test_data}")
        sys.exit(1)

    if not args.model.exists():
        print(f"Error: Model file not found: {args.model}")
        sys.exit(1)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Load extractor
    print(f"Loading model from {args.model}...")
    extractor = EmailBodyExtractor()
    extractor.load_model(args.model)

    # Load test data
    print(f"Loading test data from {args.test_data}...")
    with open(args.test_data) as f:
        examples = [json.loads(line) for line in f]
    print(f"Loaded {len(examples)} examples")

    # Find confident wrong examples
    print("Finding confident wrong examples...")
    confident_wrong = []
    for i, ex in enumerate(examples):
        try:
            result = extractor.extract_with_metadata(ex["email_text"])
            if result is None or result.body is None:
                continue
            expected = get_expected_body(ex["lines"])
            extracted_norm = normalize_text(result.body)
            expected_norm = normalize_text(expected)
            if extracted_norm != expected_norm:
                # Get ground truth labels
                ground_truth = [(item["text"], item["label"]) for item in ex["lines"]]
                confident_wrong.append(
                    {
                        "index": i,
                        "template": ex["metadata"].get("template_type", "unknown"),
                        "email": ex["email_text"],
                        "expected": expected,
                        "extracted": result.body,
                        "confidence": result.confidence,
                        "predicted": [
                            (ln.text, ln.label, ln.confidence)
                            for ln in result.labeled_lines
                        ],
                        "ground_truth": ground_truth,
                    }
                )
        except ExtractionError:
            pass

    print(f"Found {len(confident_wrong)} confident wrong examples")

    # Write to file
    with open(args.output, "w") as f:
        f.write(f"Confident Wrong Examples: {len(confident_wrong)} total\n")
        f.write("=" * 100 + "\n\n")

        for i, ex in enumerate(confident_wrong[: args.limit]):
            f.write(
                f"Example #{i+1} (index {ex['index']}, template: {ex['template']}, conf: {ex['confidence']:.3f})\n"
            )
            f.write("-" * 100 + "\n")

            # Show labels side by side: predicted vs ground truth
            f.write("LABELS (Predicted vs Ground Truth):\n")
            f.write(f"  {'Predicted':<12} {'Conf':>5}  {'Truth':<12}  Text\n")
            f.write(f"  {'-'*12} {'-'*5}  {'-'*12}  {'-'*60}\n")

            predicted = ex["predicted"]
            ground_truth = ex["ground_truth"]

            # Align by normalized text (predicted is normalized, ground truth is not)
            for j, (pred_text, pred_label, pred_conf) in enumerate(predicted):
                # Find matching ground truth (same index, since normalization preserves line count)
                if j < len(ground_truth):
                    gt_text, gt_label = ground_truth[j]
                else:
                    gt_label = "?"

                # Highlight mismatches
                match_marker = " " if pred_label == gt_label else "*"
                text_display = pred_text[:55] + "..." if len(pred_text) > 55 else pred_text
                f.write(
                    f"{match_marker} {pred_label:<12} {pred_conf:>5.2f}  {gt_label:<12}  {text_display}\n"
                )

            f.write("-" * 50 + "\n")
            f.write("EXPECTED:\n")
            f.write(ex["expected"] + "\n")
            f.write("-" * 50 + "\n")
            f.write("EXTRACTED:\n")
            f.write(ex["extracted"] + "\n")
            f.write("=" * 100 + "\n\n")

    print(f"Wrote {min(args.limit, len(confident_wrong))} examples to {args.output}")


if __name__ == "__main__":
    main()
