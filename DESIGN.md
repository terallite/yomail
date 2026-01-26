# yomail (読メール): Japanese Email Body Extractor

## Original Design Specification v1.0

> **Note:** This document is the **original design specification** created before implementation. It is preserved for historical reference and to document the original requirements and design rationale.
>
> For the **current as-built implementation**, see [ARCHITECTURE.md](ARCHITECTURE.md).
>
> Key differences from implementation are documented in ARCHITECTURE.md's "Design Deviations" section.

---

## 1. Overview

A lightweight, fast, and highly robust system to extract body text from Japanese business emails. Designed for production deployment with emphasis on accuracy and graceful failure handling.

### 1.1 Success Criteria

| Metric                                | Target                          |
| ------------------------------------- | ------------------------------- |
| Accuracy on unambiguous body content  | 99.99%                          |
| Graceful failure on off-nominal input | Fail static (exception or null) |
| Latency (hot state)                   | < 500ms                         |
| Memory footprint                      | < 1 GB                          |
| Training time (if needed)             | < 2 hours on MacBook 32GB RAM   |

### 1.2 Scope

**In scope:**

- Japanese business emails (formal and informal)
- Emails with complex structure (forwarded, replied, inline quotes)
- Edge cases: mobile replies, no-body forwards, emails discussing emails

**Out of scope:**

- Non-Japanese emails (should fail gracefully)
- Non-email text (should fail gracefully)
- HTML email rendering (expects plain text or pre-extracted text)

---

## 2. Architecture

### 2.1 Pipeline Overview

```
RAW EMAIL
    │
    ▼
┌─────────────────────────────────────┐
│  NORMALIZER                         │
│  - Encoding normalization           │
│  - Unicode normalization (NFKC)     │
│  - Header stripping                 │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  STRUCTURAL ANALYZER                │
│  - Quote depth tracking             │
│  - Quote block boundaries           │
│  - Forward/reply header detection   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  FEATURE EXTRACTOR                  │
│  - Positional features              │
│  - Content features                 │
│  - Pattern match flags              │
│  - Contextual window features       │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  CRF SEQUENCE LABELER               │
│  - Per-line label prediction        │
│  - Marginal probability output      │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  BODY ASSEMBLER                     │
│  - Signature boundary detection     │
│  - Inline quote classification      │
│  - Block merging logic              │
│  - No-signature fallback            │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  CONFIDENCE GATE                    │
│  - Threshold check                  │
│  - Ambiguity detection              │
│  - Exception raising                │
└─────────────────────────────────────┘
    │
    ▼
EXTRACTED BODY or EXCEPTION
```

### 2.2 Design Rationale: Why CRF?

The CRF (Conditional Random Field) approach was chosen over pure heuristics or neural models based on the following constraints:

| Factor             | CRF Advantage                            |
| ------------------ | ---------------------------------------- |
| Training data      | Works well with 1-5K synthetic examples  |
| Domain knowledge   | Easy to inject via hand-crafted features |
| Training time      | Minutes, not hours                       |
| Inference speed    | 10-30ms typical                          |
| Memory             | Model ~5MB                               |
| Sequence structure | Naturally models label transitions       |

Neural approaches require more data and risk overfitting to synthetic patterns. Pure heuristics lack adaptability to edge cases.

---

## 3. Component Specifications

> **See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed as-built component specifications.**

The implementation includes these pipeline stages:

1. **Normalizer** — Line endings, neologdn, NFKC normalization
2. **Content Filter** — Separates blank lines from content (added during implementation)
3. **Structural Analyzer** — Quote depth, forward/reply headers
4. **Feature Extractor** — 37 features per line for ML
5. **CRF Sequence Labeler** — Per-line label prediction with post-processing
6. **Reconstructor** — Reinserts blank lines (added during implementation)
7. **Body Assembler** — Signature boundary detection, block building
8. **Confidence Check** — Viterbi sequence probability threshold

**Label scheme:** GREETING, BODY, CLOSING, SIGNATURE, QUOTE, OTHER

---

## 4. Pattern Databases

> **See source code in `src/yomail/patterns/` for actual patterns.**

Pattern modules implemented:
- `greetings.py` — Japanese email opening formulas
- `closings.py` — Japanese email closing formulas
- `signatures.py` — Contact info, company names, positions
- `separators.py` — Visual delimiter detection
- `names.py` — Japanese name detection

All patterns match against neologdn-normalized text.

---

## 5. Public Interface

> **See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed API documentation.**

```python
from yomail import EmailBodyExtractor

extractor = EmailBodyExtractor(confidence_threshold=0.5)

# Strict - raises on failure
body = extractor.extract(email_text)

# Safe - returns None on failure
body = extractor.extract_safe(email_text)

# Full metadata
result = extractor.extract_with_metadata(email_text)
```

**Exceptions:** `ExtractionError` (base), `InvalidInputError`, `NoBodyDetectedError`, `LowConfidenceError`

---

## 6. Command Line Interface

> **Status:** Not implemented. The original design specified a CLI, but it was not prioritized for the initial release. Library usage is the primary interface.

---

## 7. Training Data Interface

Training data is provided by an external synthetic data generator project.

### 7.1 Format

JSONL file, one example per line.

**Example structure:**

- email_text: str (raw email, headers stripped)
- line_labels: List of {text, label, quote_depth}
- metadata: {template_type, has_signature, has_inline_quote, is_adversarial, ...}

### 7.2 Expected Distribution

| Template Type | Percentage |
| ------------- | ---------- |
| formal_full   | 60%        |
| informal      | 15%        |
| mobile_reply  | 10%        |
| forward_only  | 5%         |
| inline_quote  | 5%         |
| adversarial   | 5%         |

### 7.3 Training Script

The project should include a training script that:

- Loads JSONL training data
- Extracts features using the Feature Extractor
- Trains CRF model
- Saves model to `models/` directory
- Reports training metrics

---

## 8. Evaluation

### 8.1 Validation Approach

Real data (containing PII) is used for validation only, never training. This creates a feedback loop:

1. Train on synthetic data
2. Evaluate on real data
3. Analyze failures
4. Improve synthetic generator to cover failure modes
5. Repeat

### 8.2 Metrics

**Primary:**

- Exact match rate
- Acceptable extraction rate (minor over/under extraction within 10%)

**Secondary:**

- False positive rate (extracted wrong content)
- False negative rate (should have succeeded, raised exception)
- Correct rejection rate (should have failed, did fail)

### 8.3 Acceptable Extraction Definition

An extraction is "acceptable" if:

- Expected body is substring of extracted (slight over-extraction), OR
- Extracted is substring of expected (slight under-extraction)
- AND difference is < 10% of expected length

---

## 9. Installation and Integration

> **See [README.md](README.md) for current installation instructions.**

```
pip install yomail
```

Configuration is via constructor parameters:

```python
extractor = EmailBodyExtractor(
    model_path="path/to/model.crfsuite",  # Optional custom model
    confidence_threshold=0.5,              # Minimum confidence
)
```

> **Note:** Environment variable configuration (`YOMAIL_CONFIDENCE_THRESHOLD`, `YOMAIL_LOG_LEVEL`) was specified in the original design but not implemented.

---

## 10. Project Structure

> **See [ARCHITECTURE.md](ARCHITECTURE.md) for the current module structure.**

The actual implementation differs from the original design:
- Added `content_filter.py` and `reconstructor.py` to pipeline
- Pattern modules: `greetings.py`, `closings.py`, `signatures.py`, `separators.py`, `names.py` (no `quotes.py`)
- Tests are flat in `tests/` (not split into `unit/` and `integration/`)

---

## 11. Code Quality Standards

Inference code (`src/`) runs in production and requires stricter standards than training scripts.

### 11.1 Inference Code (`src/`)

| Aspect           | Requirement                           |
| ---------------- | ------------------------------------- |
| Type hints       | Complete, strict                      |
| Test coverage    | High (90%+)                           |
| Assertions       | Forbidden — use explicit exceptions   |
| Print statements | Forbidden — use logging               |
| Docstrings       | Required on public API                |
| Error handling   | Explicit, defensive, no bare `except` |
| Dependencies     | Minimal, pinned                       |

### 11.2 Training Code (`scripts/`)

| Aspect           | Requirement      |
| ---------------- | ---------------- |
| Type hints       | Optional         |
| Test coverage    | Not enforced     |
| Assertions       | Allowed          |
| Print statements | Allowed          |
| Docstrings       | Optional         |
| Error handling   | Can raise freely |

### 11.3 Enforcement

Tooling configuration should enforce different rules per directory. The implementer may choose appropriate linting, type checking, and testing tools, configured to respect the above split.

## 12. Dependencies

> **See `pyproject.toml` for actual dependencies.**

**Original design specified:**
- sklearn-crfsuite (CRF implementation) → **Implemented with python-crfsuite** (sklearn-crfsuite unmaintained)
- pydantic (data validation) → **Not used** (dataclasses used instead)
- regex (Unicode support) → **Not used** (standard `re` sufficient)

**Actual runtime dependencies:**
- neologdn (Japanese text normalization)
- python-crfsuite (CRF implementation)
- pyyaml (name data loading)

---

## 13. Resolved Implementation Questions

The following questions from the original design have been resolved:

1. **Encoding detection:** Not implemented; assumes UTF-8 input
2. **CRF library:** python-crfsuite (sklearn-crfsuite is unmaintained)
3. **neologdn options:** Default settings with custom delimiter line handling
4. **Pattern database format:** Compiled regex objects at module load time
5. **Feature normalization:** No standardization; raw values work well with CRF
6. **Model versioning:** Single bundled model at `src/yomail/data/email_body.crfsuite`

---

## Appendix A: Label Transition Intuitions

Expected transition probabilities (to guide training interpretation):

| From → To             | Expected Frequency              |
| --------------------- | ------------------------------- |
| GREETING → BODY       | High                            |
| GREETING → GREETING   | Low (multi-line greetings rare) |
| BODY → BODY           | Very high                       |
| BODY → CLOSING        | Medium                          |
| BODY → SIGNATURE      | Low (usually through CLOSING)   |
| CLOSING → SIGNATURE   | High                            |
| SIGNATURE → SIGNATURE | Very high                       |
| SIGNATURE → BODY      | Very low (key constraint)       |
| QUOTE → QUOTE         | Very high                       |
| OTHER → BODY          | Medium                          |
| OTHER → SIGNATURE     | Medium                          |

---

## Appendix B: Adversarial Cases to Test

1. Body discusses proper signature format with example signature
2. Body quotes a business card verbatim
3. Body contains contact information as content (e.g., "please update your records with my new phone: ...")
4. Email forwards another email that has a signature, outer email has no body
5. Interleaved reply (content, quote, content, quote, content)
6. Mobile reply: single line, no greeting, no signature
7. Very long signature (10+ lines)
8. No clear separator before signature
9. Signature-like content in greeting (e.g., formal letter with sender's title)
10. Multiple forwarded emails nested
