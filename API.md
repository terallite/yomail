# API Reference

This document provides a quick reference for yomail's public API.

## Quick Start

```python
from yomail import EmailBodyExtractor

extractor = EmailBodyExtractor()
content = extractor.extract(email_text)  # Returns greeting + body + closing
```

---

## Main Interface

### EmailBodyExtractor

The primary class for extracting message content from Japanese emails.

**What gets extracted:** GREETING + BODY + CLOSING lines (and inline quotes between them).

**What gets excluded:** SIGNATURE, leading/trailing QUOTE, and OTHER lines.

```python
from yomail import EmailBodyExtractor
```

#### Constructor

```python
EmailBodyExtractor(
    model_path: Path | str | None = None,  # Custom model path (default: bundled model)
    confidence_threshold: float = 0.5,      # Minimum confidence to accept
)
```

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `extract(email_text: str)` | `str` | Extract message content. Raises on failure. |
| `extract_safe(email_text: str)` | `str \| None` | Extract message content. Returns `None` on failure. |
| `extract_with_metadata(email_text: str)` | `ExtractionResult` | Extract with full metadata. |
| `load_model(model_path: Path \| str)` | `None` | Load a custom CRF model. |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_model_loaded` | `bool` | Whether a model is currently loaded. |

---

### ExtractionResult

Returned by `extract_with_metadata()`. Contains the extracted content and debugging information.

```python
from yomail import ExtractionResult
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `body` | `str \| None` | Extracted message content (greeting + body + closing), or `None` if failed. |
| `confidence` | `float` | Confidence score (0.0 to 1.0). |
| `success` | `bool` | Whether extraction succeeded. |
| `error` | `ExtractionError \| None` | Error if failed, `None` otherwise. |
| `labeled_lines` | `tuple[LabeledLine, ...]` | All lines with labels (for debugging). |
| `signature_detected` | `bool` | Whether a signature was found. |
| `inline_quotes_included` | `int` | Number of inline quote lines in body. |

---

## Exceptions

All exceptions inherit from `ExtractionError`.

```python
from yomail import (
    ExtractionError,
    InvalidInputError,
    NoBodyDetectedError,
    LowConfidenceError,
)
```

| Exception | Attributes | Raised When |
|-----------|------------|-------------|
| `ExtractionError` | — | Base class for all errors. |
| `InvalidInputError` | `message: str` | Input is empty or invalid. |
| `NoBodyDetectedError` | `message: str` | No body content found. |
| `LowConfidenceError` | `message: str`, `confidence: float`, `threshold: float` | Confidence below threshold. |

---

## Labels

Lines are classified into one of six labels:

```python
from yomail import Label, LABELS

# Label is a Literal type
Label = Literal["GREETING", "BODY", "CLOSING", "SIGNATURE", "QUOTE", "OTHER"]

# LABELS is a tuple of all valid labels
LABELS: tuple[Label, ...] = ("GREETING", "BODY", "CLOSING", "SIGNATURE", "QUOTE", "OTHER")
```

| Label | Description | Example | Included in output? |
|-------|-------------|---------|---------------------|
| `GREETING` | Opening formulas | お世話になっております | Yes |
| `BODY` | Main content | 資料を添付いたします | Yes |
| `CLOSING` | Closing formulas | よろしくお願いいたします | Yes |
| `SIGNATURE` | Sender information | 山田太郎 / TEL: 03-1234-5678 | No |
| `QUOTE` | Quoted content | > 前回のメール内容 | Inline only* |
| `OTHER` | Separators, noise | ────────── | Between content only |

*Inline quotes (with content before AND after) are included; leading/trailing quotes are excluded.

---

## Pipeline Components

For advanced use cases, individual pipeline components are available.

```python
from yomail import (
    # Normalization
    Normalizer,
    NormalizedEmail,

    # Content filtering
    ContentFilter,
    ContentLine,
    FilteredContent,
    WhitespaceMap,

    # Structural analysis
    StructuralAnalyzer,
    StructuralAnalysis,
    AnnotatedLine,

    # Feature extraction
    FeatureExtractor,
    ExtractedFeatures,
    LineFeatures,

    # CRF labeling
    CRFSequenceLabeler,
    CRFTrainer,
    SequenceLabelingResult,
    LabeledLine,

    # Reconstruction
    Reconstructor,
    ReconstructedDocument,
    ReconstructedLine,

    # Body assembly
    BodyAssembler,
    AssembledBody,
)
```

### Pipeline Overview

```
email_text
    │
    ▼
┌─────────────┐
│ Normalizer  │ → NormalizedEmail
└─────────────┘
    │
    ▼
┌───────────────┐
│ ContentFilter │ → FilteredContent (removes blank lines)
└───────────────┘
    │
    ▼
┌────────────────────┐
│ StructuralAnalyzer │ → StructuralAnalysis (quote depth, delimiters)
└────────────────────┘
    │
    ▼
┌──────────────────┐
│ FeatureExtractor │ → ExtractedFeatures (37 features per line)
└──────────────────┘
    │
    ▼
┌────────────────────┐
│ CRFSequenceLabeler │ → SequenceLabelingResult (labels + probabilities)
└────────────────────┘
    │
    ▼
┌───────────────┐
│ Reconstructor │ → ReconstructedDocument (reinserts blank lines)
└───────────────┘
    │
    ▼
┌───────────────┐
│ BodyAssembler │ → AssembledBody (final text)
└───────────────┘
```

### Normalizer

Normalizes Japanese email text (line endings, neologdn, NFKC).

```python
normalizer = Normalizer()
result: NormalizedEmail = normalizer.normalize(text)

result.lines  # tuple[str, ...] - normalized lines
result.text   # str - full text with newlines
```

### StructuralAnalyzer

Analyzes quote depth and structural elements.

```python
analyzer = StructuralAnalyzer()
result: StructuralAnalysis = analyzer.analyze(filtered_content)

result.lines              # tuple[AnnotatedLine, ...]
result.has_quotes         # bool
result.has_forward_reply  # bool
result.first_quote_index  # int | None
result.last_quote_index   # int | None
```

### CRFSequenceLabeler

Predicts labels using the CRF model.

```python
labeler = CRFSequenceLabeler()  # Loads bundled model
labeler = CRFSequenceLabeler(model_path="custom.crfsuite")
labeler = CRFSequenceLabeler(use_default=False)  # No model loaded

result: SequenceLabelingResult = labeler.predict(features, texts)

result.labeled_lines        # tuple[LabeledLine, ...]
result.sequence_probability # float (Viterbi probability)
```

### CRFTrainer

Train custom CRF models.

```python
trainer = CRFTrainer(
    algorithm="lbfgs",      # lbfgs, l2sgd, ap, pa, arow
    c1=0.1,                 # L1 regularization
    c2=0.1,                 # L2 regularization
    max_iterations=100,
    all_possible_transitions=True,
)

trainer.add_sequence(features, texts, labels)
trainer.train("output.crfsuite")
```

### LabeledLine

Individual line with prediction results.

```python
line: LabeledLine

line.text                # str - original text
line.label               # Label - predicted label
line.confidence          # float - marginal probability
line.label_probabilities # dict[Label, float] - all label probabilities
```

---

## Pattern Utilities

Low-level pattern matching functions used internally. Available from `yomail.patterns`:

```python
from yomail.patterns import (
    is_greeting_line,     # Detects greetings (お世話になっております)
    is_closing_line,      # Detects closings (よろしくお願いします)
    is_separator_line,    # Detects visual separators (──────)
    is_contact_info_line, # Detects phone/fax/email/URL
    is_company_line,      # Detects company names (株式会社)
)
```

All functions have the signature:

```python
def is_*_line(line: str) -> bool: ...
```

---

## Type Hints

yomail is fully typed and PEP 561 compliant. Type checkers will automatically discover types from the installed package.

```python
# Types are available for import
from yomail import Label, ExtractionResult, LabeledLine

def process_email(text: str) -> str | None:
    extractor = EmailBodyExtractor()
    result: ExtractionResult = extractor.extract_with_metadata(text)
    return result.body
```
