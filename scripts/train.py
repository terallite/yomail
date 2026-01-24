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

from yomail.pipeline.crf import CRFTrainer, Label, LABELS
from yomail.pipeline.features import FeatureExtractor
from yomail.pipeline.normalizer import Normalizer
from yomail.pipeline.structural import StructuralAnalyzer


def load_training_data(path: Path) -> list[dict]:
    """Load training data from JSONL file.

    Expected format per line:
    {
        "email_text": "...",
        "line_labels": [
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
            line_labels_raw = example["line_labels"]

            # Extract labels
            labels = validate_labels([item["label"] for item in line_labels_raw])

            # Run through pipeline
            # Note: We use the raw texts, not the normalized ones,
            # because the training data should already have matching line structure
            normalized = normalizer.normalize(email_text)

            # Verify line count matches
            if len(normalized.lines) != len(labels):
                print(
                    f"Warning: Example {i+1} has {len(normalized.lines)} lines "
                    f"after normalization but {len(labels)} labels. Skipping."
                )
                failed += 1
                continue

            structural = structural_analyzer.analyze(normalized)
            features = feature_extractor.extract(structural)

            # Add to trainer
            trainer.add_sequence(features, normalized.lines, tuple(labels))

            # Count labels
            for label in labels:
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
