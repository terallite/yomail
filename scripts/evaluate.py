#!/usr/bin/env python3
"""Evaluation script for CRF email body extraction model.

Loads test data, runs the extractor, and computes metrics as specified
in DESIGN.md Section 8.

Usage:
    python scripts/evaluate.py data/test.jsonl
    python scripts/evaluate.py data/test.jsonl --model models/custom.crfsuite
    python scripts/evaluate.py data/test.jsonl --verbose
"""

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from yomail import EmailBodyExtractor
from yomail.pipeline.crf import LABELS, Label
from yomail.pipeline.normalizer import Normalizer

# Shared normalizer for expected body computation
_normalizer = Normalizer()


@dataclass
class ExtractionEvaluation:
    """Evaluation result for a single extraction."""

    # Input/output
    email_text: str
    expected_body: str
    extracted_body: str | None

    # Classification
    success: bool
    exact_match: bool
    acceptable: bool

    # Details
    confidence: float
    error_type: str | None
    metadata: dict


@dataclass
class LabelMetrics:
    """Per-label accuracy metrics."""

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)

    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace for content comparison."""
    # Split into non-empty lines, strip each, rejoin with single newlines
    lines = [line.strip() for line in text.strip().split("\n")]
    # Remove empty lines and rejoin
    return "\n".join(line for line in lines if line)


@dataclass
class EvaluationResults:
    """Aggregated evaluation results."""

    total: int = 0
    successful: int = 0
    exact_matches: int = 0
    content_matches: int = 0  # Matches after whitespace normalization
    acceptable: int = 0
    failed: int = 0

    # Error breakdown
    errors_by_type: Counter = field(default_factory=Counter)

    # Label-level metrics
    label_metrics: dict[Label, LabelMetrics] = field(default_factory=dict)

    # Confidence distribution
    confidences: list[float] = field(default_factory=list)

    # Failed examples for analysis
    failures: list[ExtractionEvaluation] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successful / self.total if self.total > 0 else 0.0

    @property
    def exact_match_rate(self) -> float:
        return self.exact_matches / self.total if self.total > 0 else 0.0

    @property
    def content_match_rate(self) -> float:
        return self.content_matches / self.total if self.total > 0 else 0.0

    @property
    def acceptable_rate(self) -> float:
        return self.acceptable / self.total if self.total > 0 else 0.0

    @property
    def avg_confidence(self) -> float:
        return sum(self.confidences) / len(self.confidences) if self.confidences else 0.0


def is_acceptable_extraction(expected: str, extracted: str) -> bool:
    """Check if extraction is acceptable per DESIGN.md Section 8.3.

    An extraction is "acceptable" if:
    - Expected body is substring of extracted (slight over-extraction), OR
    - Extracted is substring of expected (slight under-extraction)
    - AND difference is < 10% of expected length
    """
    if not expected or not extracted:
        return False

    # Normalize whitespace for comparison
    expected_norm = expected.strip()
    extracted_norm = extracted.strip()

    if expected_norm == extracted_norm:
        return True

    # Check substring relationship
    is_over_extraction = expected_norm in extracted_norm
    is_under_extraction = extracted_norm in expected_norm

    if not (is_over_extraction or is_under_extraction):
        return False

    # Check 10% threshold
    diff = abs(len(extracted_norm) - len(expected_norm))
    threshold = len(expected_norm) * 0.1

    return diff <= threshold


def get_expected_body(example: dict) -> str:
    """Extract expected body from training example.

    Computes expected body the same way BodyAssembler does:
    - Include GREETING, BODY, CLOSING, and intervening OTHER (separators)
    - Stop at first SIGNATURE line
    - Exclude trailing/leading QUOTE lines
    - Include inline QUOTE lines (quotes between BODY content)

    Also normalizes text the same way the extractor does.
    """
    lines_data = example.get("lines") or example.get("line_labels", [])

    # Normalize the line texts the same way the extractor does
    normalized_lines = []
    for item in lines_data:
        text = item["text"]
        if not text or not text.strip():
            # Empty lines stay empty
            normalized_lines.append({"text": "", "label": item["label"]})
        else:
            try:
                # Apply normalizer to each line
                normalized = _normalizer.normalize(text)
                # The normalizer splits into lines, so join them back
                normalized_text = "\n".join(normalized.lines) if normalized.lines else ""
                normalized_lines.append({"text": normalized_text, "label": item["label"]})
            except Exception:
                # If normalization fails, use original text
                normalized_lines.append({"text": text, "label": item["label"]})
    lines_data = normalized_lines

    if not lines_data:
        return ""

    # Find signature boundary
    signature_index = None
    for idx, item in enumerate(lines_data):
        if item["label"] == "SIGNATURE":
            signature_index = idx
            break

    end_index = signature_index if signature_index is not None else len(lines_data)

    # Find BODY line indices to determine inline vs trailing quotes
    body_indices = [i for i, item in enumerate(lines_data[:end_index]) if item["label"] == "BODY"]

    if len(body_indices) < 2:
        first_body = body_indices[0] if body_indices else -1
        last_body = body_indices[-1] if body_indices else -1
    else:
        first_body = body_indices[0]
        last_body = body_indices[-1]

    # Build content blocks (mimicking BodyAssembler logic)
    content_labels = {"GREETING", "BODY", "CLOSING"}
    blocks: list[list[str]] = []
    current_block: list[str] = []
    separator_buffer: list[str] = []

    for idx in range(end_index):
        item = lines_data[idx]
        label = item["label"]
        text = item["text"]

        if label in content_labels:
            # Flush separator buffer
            current_block.extend(separator_buffer)
            separator_buffer = []
            current_block.append(text)

        elif label == "OTHER":
            # Buffer separators (blank lines, etc.)
            separator_buffer.append(text)

        elif label == "QUOTE":
            # Only include if inline (between first and last BODY)
            if first_body < idx < last_body:
                current_block.extend(separator_buffer)
                separator_buffer = []
                current_block.append(text)
            else:
                # Trailing/leading quote - hard break
                if current_block:
                    blocks.append(current_block)
                    current_block = []
                separator_buffer = []

    # Flush remaining block
    if current_block:
        blocks.append(current_block)

    # Select body (all blocks if signature present, longest otherwise)
    if signature_index is not None:
        selected_lines: list[str] = []
        for block in blocks:
            selected_lines.extend(block)
    else:
        selected_lines = max(blocks, key=len) if blocks else []

    return "\n".join(selected_lines)


def get_ground_truth_labels(example: dict) -> list[Label]:
    """Extract ground truth labels from training example."""
    lines_data = example.get("lines") or example.get("line_labels", [])
    return [item["label"] for item in lines_data]


def load_test_data(path: Path) -> list[dict]:
    """Load test data from JSONL file."""
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


def evaluate_single(
    extractor: EmailBodyExtractor,
    example: dict,
    results: EvaluationResults,
    verbose: bool = False,
) -> ExtractionEvaluation:
    """Evaluate extraction on a single example."""
    email_text = example["email_text"]
    expected_body = get_expected_body(example)
    metadata = example.get("metadata", {})
    ground_truth_labels = get_ground_truth_labels(example)

    # Run extraction
    result = extractor.extract_with_metadata(email_text)

    # Determine outcome
    extracted = result.body
    success = result.success
    exact_match = False
    acceptable = False
    error_type = None

    if success and extracted:
        exact_match = extracted.strip() == expected_body.strip()
        content_match = normalize_whitespace(extracted) == normalize_whitespace(expected_body)
        acceptable = is_acceptable_extraction(expected_body, extracted)
        results.successful += 1
        results.confidences.append(result.confidence)

        if exact_match:
            results.exact_matches += 1
        if content_match:
            results.content_matches += 1
        if acceptable:
            results.acceptable += 1
    else:
        results.failed += 1
        if result.error:
            error_type = type(result.error).__name__
            results.errors_by_type[error_type] += 1

    # Compute label-level metrics
    predicted_labels = [line.label for line in result.labeled_lines]

    # Only compute if line counts match
    if len(predicted_labels) == len(ground_truth_labels):
        for pred, truth in zip(predicted_labels, ground_truth_labels, strict=True):
            if pred not in results.label_metrics:
                results.label_metrics[pred] = LabelMetrics()
            if truth not in results.label_metrics:
                results.label_metrics[truth] = LabelMetrics()

            if pred == truth:
                results.label_metrics[pred].true_positives += 1
            else:
                results.label_metrics[pred].false_positives += 1
                results.label_metrics[truth].false_negatives += 1

    evaluation = ExtractionEvaluation(
        email_text=email_text,
        expected_body=expected_body,
        extracted_body=extracted,
        success=success,
        exact_match=exact_match,
        acceptable=acceptable,
        confidence=result.confidence,
        error_type=error_type,
        metadata=metadata,
    )

    # Track failures for analysis (only significant failures, not whitespace differences)
    content_match = success and extracted and normalize_whitespace(extracted) == normalize_whitespace(expected_body)
    if not content_match:
        results.failures.append(evaluation)

    if verbose and not content_match:
        template_type = metadata.get("template_type", "unknown")
        print(f"\n--- Failure ({template_type}) ---")
        print(f"Expected body ({len(expected_body)} chars):")
        print(expected_body[:200] + "..." if len(expected_body) > 200 else expected_body)
        print(f"\nExtracted ({len(extracted) if extracted else 0} chars):")
        if extracted:
            print(extracted[:200] + "..." if len(extracted) > 200 else extracted)
        else:
            print(f"(None - {error_type})")
        print()

    return evaluation


def print_results(results: EvaluationResults):
    """Print evaluation results summary."""
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    # Primary metrics
    print("\n--- Primary Metrics ---")
    print(f"Total examples:      {results.total}")
    print(f"Success rate:        {100 * results.success_rate:.2f}% ({results.successful}/{results.total})")
    print(f"Exact match rate:    {100 * results.exact_match_rate:.2f}% ({results.exact_matches}/{results.total})")
    print(f"Content match rate:  {100 * results.content_match_rate:.2f}% ({results.content_matches}/{results.total})")
    print(f"Acceptable rate:     {100 * results.acceptable_rate:.2f}% ({results.acceptable}/{results.total})")

    # Confidence stats
    if results.confidences:
        confidences = sorted(results.confidences)
        print(f"\n--- Confidence Distribution ---")
        print(f"Mean:    {results.avg_confidence:.3f}")
        print(f"Min:     {min(confidences):.3f}")
        print(f"Max:     {max(confidences):.3f}")
        print(f"Median:  {confidences[len(confidences) // 2]:.3f}")
        print(f"P10:     {confidences[int(len(confidences) * 0.1)]:.3f}")
        print(f"P90:     {confidences[int(len(confidences) * 0.9)]:.3f}")

    # Error breakdown
    if results.errors_by_type:
        print(f"\n--- Error Breakdown ---")
        for error_type, count in results.errors_by_type.most_common():
            print(f"  {error_type}: {count}")

    # Per-label metrics
    if results.label_metrics:
        print(f"\n--- Per-Label Metrics ---")
        print(f"{'Label':<12} {'Precision':>10} {'Recall':>10} {'F1':>10}")
        print("-" * 44)
        for label in LABELS:
            if label in results.label_metrics:
                m = results.label_metrics[label]
                print(f"{label:<12} {m.precision:>10.3f} {m.recall:>10.3f} {m.f1:>10.3f}")

    # Failure analysis by template type
    if results.failures:
        print(f"\n--- Failures by Template Type ---")
        failure_types = Counter(f.metadata.get("template_type", "unknown") for f in results.failures)
        for template_type, count in failure_types.most_common():
            print(f"  {template_type}: {count}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate CRF email body extraction model"
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
        "--verbose",
        "-v",
        action="store_true",
        help="Print details for each failure",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Limit number of examples to evaluate",
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.test_data.exists():
        print(f"Error: Test data file not found: {args.test_data}")
        sys.exit(1)

    if not args.model.exists():
        print(f"Error: Model file not found: {args.model}")
        sys.exit(1)

    # Load data
    print(f"Loading test data from {args.test_data}...")
    examples = load_test_data(args.test_data)
    print(f"Loaded {len(examples)} test examples")

    if args.limit:
        examples = examples[:args.limit]
        print(f"Limiting to {len(examples)} examples")

    # Initialize extractor
    print(f"Loading model from {args.model}...")
    extractor = EmailBodyExtractor(model_path=args.model)

    # Evaluate
    print("Evaluating...")
    results = EvaluationResults()

    for i, example in enumerate(examples):
        results.total += 1
        evaluate_single(extractor, example, results, verbose=args.verbose)

        # Progress indicator
        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(examples)}")

    # Print results
    print_results(results)


if __name__ == "__main__":
    main()
