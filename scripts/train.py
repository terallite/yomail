#!/usr/bin/env python3
"""Training script for CRF email body extraction model.

Loads JSONL training data, extracts features, trains CRF model,
and saves to the models/ directory.

Usage:
    python scripts/train.py data/training.jsonl
    python scripts/train.py data/training.jsonl --output models/custom.crfsuite
    python scripts/train.py data/training.jsonl --c1 0.05 --c2 0.05 --max-iter 200
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from yomail.pipeline.content_filter import ContentFilter
from yomail.pipeline.crf import CRFTrainer, Label, LABELS
from yomail.pipeline.features import FeatureExtractor
from yomail.pipeline.normalizer import Normalizer
from yomail.pipeline.structural import StructuralAnalyzer


def load_training_data(path: Path) -> list[dict]:
    """Load training data from JSONL file.

    Expected format per line (yasumail format):
    {
        "email_text": "...",
        "lines": [
            {"text": "line1", "label": "GREETING", "quote_depth": 0},
            {"text": "line2", "label": "BODY", "quote_depth": 0},
            ...
        ],
        "metadata": {...}
    }
    """
    examples = []
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                examples.append(data)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON at line {line_num}: {e}")
    return examples


def validate_labels(labels: list[str]) -> list[Label]:
    """Validate that all labels are known."""
    validated: list[Label] = []
    for label in labels:
        if label not in LABELS:
            raise ValueError(f"Unknown label: {label}. Valid labels: {LABELS}")
        validated.append(label)  # type: ignore
    return validated


def main():
    parser = argparse.ArgumentParser(
        description="Train CRF model for email body extraction"
    )
    parser.add_argument(
        "training_data",
        type=Path,
        help="Path to JSONL training data file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("models/email_body.crfsuite"),
        help="Output model path (default: models/email_body.crfsuite)",
    )
    parser.add_argument(
        "--c1",
        type=float,
        default=0.1,
        help="L1 regularization coefficient (default: 0.1)",
    )
    parser.add_argument(
        "--c2",
        type=float,
        default=0.1,
        help="L2 regularization coefficient (default: 0.1)",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=100,
        help="Maximum training iterations (default: 100)",
    )
    parser.add_argument(
        "--algorithm",
        choices=["lbfgs", "l2sgd", "ap", "pa", "arow"],
        default="lbfgs",
        help="Training algorithm (default: lbfgs)",
    )

    args = parser.parse_args()

    # Validate input file exists
    if not args.training_data.exists():
        print(f"Error: Training data file not found: {args.training_data}")
        sys.exit(1)

    # Load training data
    print(f"Loading training data from {args.training_data}...")
    examples = load_training_data(args.training_data)
    print(f"Loaded {len(examples)} training examples")

    if not examples:
        print("Error: No valid training examples found")
        sys.exit(1)

    # Initialize pipeline components
    normalizer = Normalizer()
    content_filter = ContentFilter()
    structural_analyzer = StructuralAnalyzer()
    feature_extractor = FeatureExtractor()
    trainer = CRFTrainer(
        algorithm=args.algorithm,
        c1=args.c1,
        c2=args.c2,
        max_iterations=args.max_iter,
    )

    # Process examples
    print("Extracting features...")
    successful = 0
    failed = 0
    label_counts: dict[str, int] = {label: 0 for label in LABELS}

    for i, example in enumerate(examples):
        try:
            email_text = example["email_text"]
            # Support both "lines" (yasumail) and "line_labels" (legacy) format
            lines_data = example.get("lines") or example.get("line_labels", [])

            # Extract labels
            labels = validate_labels([item["label"] for item in lines_data])

            # Run through pipeline
            normalized = normalizer.normalize(email_text)

            # Verify line count matches
            if len(normalized.lines) != len(labels):
                print(
                    f"Warning: Example {i+1} has {len(normalized.lines)} lines "
                    f"after normalization but {len(labels)} labels. Skipping."
                )
                failed += 1
                continue

            # Filter to content lines only
            filtered = content_filter.filter(normalized)

            # Filter labels to match content lines (skip labels for blank lines)
            content_labels = tuple(
                labels[idx] for idx in range(len(labels))
                if idx not in filtered.whitespace_map.blank_positions
            )

            # Verify content line count matches filtered labels
            if len(filtered.content_lines) != len(content_labels):
                print(
                    f"Warning: Example {i+1} has {len(filtered.content_lines)} content lines "
                    f"but {len(content_labels)} content labels. Skipping."
                )
                failed += 1
                continue

            structural = structural_analyzer.analyze(filtered)
            features = feature_extractor.extract(structural, filtered)

            # Add to trainer
            content_texts = tuple(line.text for line in filtered.content_lines)
            trainer.add_sequence(features, content_texts, content_labels)

            # Count labels (content labels only for accurate stats)
            for label in content_labels:
                label_counts[label] += 1

            successful += 1

        except Exception as e:
            print(f"Warning: Failed to process example {i+1}: {e}")
            failed += 1

    print(f"Successfully processed {successful} examples, {failed} failed")

    if successful == 0:
        print("Error: No examples successfully processed")
        sys.exit(1)

    # Print label distribution
    print("\nLabel distribution:")
    total_labels = sum(label_counts.values())
    for label, count in sorted(label_counts.items()):
        pct = 100 * count / total_labels if total_labels > 0 else 0
        print(f"  {label}: {count} ({pct:.1f}%)")

    # Train model
    print(f"\nTraining with algorithm={args.algorithm}, c1={args.c1}, c2={args.c2}, max_iter={args.max_iter}...")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    trainer.train(args.output)

    print(f"\nModel saved to {args.output}")
    print(f"Model size: {args.output.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
