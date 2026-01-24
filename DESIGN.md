# yomail (読メール): Japanese Email Body Extractor

## Design Specification v1.0

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

### 3.1 Normalizer

**Responsibilities:**

- Detect and convert to UTF-8
- Normalize line endings to `\n`
- Apply neologdn normalization (handles Japanese-specific normalization)
- Apply Unicode NFKC normalization (as secondary pass)
- Preserve original line structure for downstream processing

**neologdn normalization (via `neologdn.normalize()`):**

- Full-width ASCII → half-width (Ａ→A, １→1, （→(, etc.)
- Half-width katakana → full-width (ｶﾀｶﾅ→カタカナ)
- Repeated prolonged sound marks (ーーー→ー)
- Tilde/wave dash variants (~∼〜→〜)
- Various Unicode edge cases specific to Japanese text

This dramatically simplifies downstream pattern matching — patterns only need to match the canonical normalized form.

**Failure conditions:**

- Encoding detection failure → `InvalidInputError`
- Empty input after normalization → `InvalidInputError`

**Implementation notes:**

- Use charset detection library for encoding
- Apply neologdn.normalize() first, then NFKC
- Preserve blank lines (structurally meaningful)

### 3.2 Structural Analyzer

**Responsibilities:**

- Compute quote depth per line
- Identify quote block boundaries
- Detect forwarding headers and reply markers

**Quote markers to detect:**

- `>` and `＞` (full-width)
- Indentation patterns (leading spaces/tabs)
- `|` pipe quoting (less common)

**Forward/reply patterns:**

- `-----Original Message-----` and Japanese equivalents
- `On [date] [person] wrote:` patterns
- `転送:`, `Fwd:`, `Re:` in subject-like lines within body
- Delimiter lines (long sequences of `-`, `─`, `━`, `=`, etc.)

**Output:** Annotated line objects with:

- Original text
- Quote depth (0 = not quoted)
- Is forward/reply header (boolean)
- Preceding delimiter detected (boolean)

### 3.3 Feature Extractor

**Per-line features:**

_Positional:_

- Normalized position (0.0 to 1.0)
- Reverse position (distance from end, normalized)
- Lines from start (absolute)
- Lines from end (absolute)
- Position relative to first quote block
- Position relative to last quote block

_Content:_

- Line length (characters)
- Character class ratios:
  - Kanji ratio
  - Hiragana ratio
  - Katakana ratio
  - ASCII ratio
  - Digit ratio
  - Symbol/punctuation ratio
- Leading whitespace count
- Trailing whitespace count
- Is blank line (boolean)

_Pattern flags (boolean):_

- Matches greeting pattern
- Matches closing pattern
- Contains contact information pattern (tel, fax, email, URL, postal code)
- Contains company suffix pattern
- Is visual separator line
- Contains meta-discussion markers (e.g., "例えば", "以下の", "サンプル")
- Line is inside quotation marks (「」or 『』)

_Contextual (window ±2 lines):_

- Aggregate pattern flags for surrounding lines
- Blank line adjacency pattern
- Transition pattern (e.g., "blank followed by short lines")

**Feature encoding:**

- Numeric features: use directly
- Boolean features: 0/1 encoding
- Ratios: 0.0 to 1.0

### 3.4 CRF Sequence Labeler

**Label scheme:**

| Label     | Description                                             |
| --------- | ------------------------------------------------------- |
| GREETING  | Opening formulas (お世話になっております, 拝啓, etc.)   |
| BODY      | Substantive content                                     |
| CLOSING   | Closing formulas (よろしくお願いいたします, 敬具, etc.) |
| SIGNATURE | Signature block lines                                   |
| QUOTE     | Quoted content (any depth)                              |
| SEPARATOR | Visual dividers, blank lines                            |
| OTHER     | Headers, noise, unclassifiable                          |

**Model characteristics:**

- Uses sklearn-crfsuite or equivalent
- Trained on synthetic data (external generator)
- Outputs both labels and marginal probabilities per label per line
- Model file size target: < 10MB

**Training considerations:**

- L1/L2 regularization to prevent overfitting
- Cross-validation on synthetic data for hyperparameter tuning
- Stratified splits ensuring all template types represented

### 3.5 Body Assembler

**Core logic:**

1. **Find signature boundary:** Scan for first line labeled SIGNATURE. If found, all content from that line onward is excluded from body consideration.

2. **Classify quotes as inline vs trailing:**
   - A QUOTE line is "inline" if there exists BODY-labeled content both before AND after it
   - Otherwise, it is "trailing" (or "leading") and excluded from body

3. **Build content blocks:**
   - BODY lines accumulate into current block
   - SEPARATOR and OTHER lines are buffered; included if followed by more content (neutral filler)
   - Inline QUOTE lines are included in current block
   - GREETING and CLOSING lines are included if adjacent to BODY
   - Trailing/leading QUOTE lines create hard breaks

4. **Select final body:**
   - If signature was detected: concatenate all blocks before signature
   - If no signature detected: select the longest block (by line count)

5. **Assemble text:** Join selected lines preserving original line breaks

**Edge case handling:**

- Empty result after assembly → `NoBodyDetectedError`
- Multiple equally-long blocks (no signature case) → take the first one

### 3.6 Confidence Gate

**Confidence computation:**

- Base confidence: minimum marginal probability among body-labeled lines (weakest link)
- Ambiguity penalty: if high-confidence BODY labels exist outside the selected body region, reduce confidence (suggests competing valid interpretations)

**Thresholds:**

- Confidence < 0.5 → `LowConfidenceError`
- Ambiguity detection: if excluded BODY-labeled lines have confidence > 0.7, apply penalty

**Configurable:** Thresholds should be adjustable via configuration for tuning.

---

## 4. Pattern Databases

**Important:** All patterns match against neologdn-normalized text. This means:

- No need to handle full-width/half-width ASCII variants (all normalized to half-width)
- No need to handle half-width katakana (all normalized to full-width)
- No need to handle repeated prolonged sound marks

**Patterns still requiring variants** (neologdn does not collapse these):

- Different separator characters: `-`, `─`, `━`, `=`, `＝` (different codepoints, not width variants)
- Quote styles: `「」`, `『』`, `""`, `""`
- Katakana prolonged sound mark `ー` vs kanji one `一` vs hyphen `-`

### 4.1 Greeting Patterns

Common Japanese email greetings to detect (match against normalized text). Examples (non-exhaustive):

- お世話になっております
- お世話になります
- いつもお世話になっております
- 拝啓
- 前略
- お疲れ様です
- ご無沙汰しております
- 初めてご連絡いたします
- 突然のご連絡失礼いたします

**Implementation:** Regex patterns with optional variations (spacing, particles, formality levels).

### 4.2 Closing Patterns

Common closing formulas. Examples:

- よろしくお願いいたします
- よろしくお願い申し上げます
- 以上、よろしくお願いいたします
- 敬具
- 草々
- ご確認よろしくお願いいたします
- お手数をおかけしますが
- 何卒よろしくお願いいたします

### 4.3 Signature Patterns

**Visual separators (still need multiple patterns — different characters, not width variants):**

- Hyphen-minus lines: `---`
- Box drawing lines: `───`, `━━━`
- Equals lines: `===`
- Underscore lines: `___`
- Asterisk lines: `***`
- Threshold: 3+ repeated separator characters

**Contact information patterns (simplified after normalization):**

- Phone: `TEL`, `Tel`, `電話` followed by number patterns (width-normalized)
- Fax: `FAX`, `Fax`, `ファックス`
- Email: `@` with surrounding valid characters, or `E-mail:`, `Mail:`
- URL: `http://`, `https://`, `www.`
- Postal code: `〒` followed by digits, or 7-digit patterns with hyphen

**Company patterns:**

- Suffixes: 株式会社, 有限会社, 合同会社, (株), (有) — parentheses normalized to half-width
- Prefixes: 株式会社 can appear before company name

**Position patterns:**

- 部長, 課長, マネージャー, 代表, 担当, etc.

### 4.4 Quote Patterns

**Markers:**

- `>` at line start (full-width `＞` normalized to half-width)
- Multiple `>` for nested quotes
- `|` at line start
- Leading whitespace (indentation) in context of reply

**Reply/forward headers:**

- `On YYYY/MM/DD, [name] wrote:`
- `YYYY年MM月DD日 HH:MM [name] wrote:`
- `-----Original Message-----`
- `---------- Forwarded message ---------`
- Japanese equivalents

---

## 5. Public Interface

### 5.1 Main Class

```
EmailBodyExtractor
├── extract(email_text: str) → str
│   Raises: LowConfidenceError, NoBodyDetectedError, InvalidInputError
│
├── extract_safe(email_text: str) → Optional[str]
│   Returns None on any failure
│
└── extract_with_metadata(email_text: str) → ExtractionResult
    Full result with confidence, labeled lines, metadata
```

### 5.2 Result Types

**ExtractionResult:**

- body: Optional[str]
- confidence: float (0.0 - 1.0)
- success: bool
- error: Optional[ExtractionError]
- labeled_lines: List[LabeledLine] (for debugging)
- signature_detected: bool
- inline_quotes_included: int

**LabeledLine:**

- text: str
- label: str (one of the label types)
- confidence: float
- quote_depth: int

### 5.3 Exceptions

All inherit from base `ExtractionError`:

- `LowConfidenceError`: Model confidence below threshold
- `NoBodyDetectedError`: No body content found
- `InvalidInputError`: Input not valid email or not Japanese

---

## 6. Command Line Interface

Optional CLI for debugging and one-off extraction.

### 6.1 Basic Usage

```
# Read from stdin
cat email.txt | python -m yomail

# Read from file
python -m yomail email.txt

# Output to file
python -m yomail email.txt -o body.txt
```

### 6.2 Options

- `-o, --output FILE`: Write output to file instead of stdout
- `--mode {strict,safe,full}`: Extraction mode (default: strict)
- `--confidence-threshold FLOAT`: Override default confidence threshold
- `-v, --verbose`: Enable debug logging
- `--version`: Show version and exit

### 6.3 Exit Codes

- `0`: Success
- `1`: Extraction failed (low confidence, no body, invalid input)
- `2`: Invalid arguments / usage error

### 6.4 Full Mode Output

When `--mode full` is specified, output is JSON:

```json
{
  "body": "extracted text",
  "confidence": 0.87,
  "signature_detected": true,
  "inline_quotes_included": 1
}
```

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

### 9.1 Installation

```
pip install yomail
```

Or with training dependencies:

```
pip install yomail[train]
```

### 9.2 Library Usage

```python
from yomail import EmailBodyExtractor

extractor = EmailBodyExtractor()

# Simple extraction
body = extractor.extract(email_text)

# Safe extraction (returns None on failure)
body = extractor.extract_safe(email_text)

# Full metadata
result = extractor.extract_with_metadata(email_text)
```

### 9.3 Configuration

Environment variables (or pass to constructor):

- `YOMAIL_CONFIDENCE_THRESHOLD`: float, default 0.5
- `YOMAIL_LOG_LEVEL`: DEBUG/INFO/WARNING/ERROR

### 9.4 Resource Targets

| Resource                 | Target                     |
| ------------------------ | -------------------------- |
| Package size (installed) | < 20MB                     |
| Runtime memory           | < 100MB typical, < 1GB max |
| Cold import              | < 2s                       |
| Hot latency              | < 500ms                    |

---

## 10. Project Structure

```
yomail/
├── src/
│   └── yomail/
│       ├── __init__.py
│       ├── extractor.py          # Main EmailBodyExtractor
│       ├── pipeline/
│       │   ├── normalizer.py
│       │   ├── structural.py
│       │   ├── features.py
│       │   ├── crf.py
│       │   └── assembler.py
│       ├── patterns/
│       │   ├── greetings.py
│       │   ├── closings.py
│       │   ├── signatures.py
│       │   └── quotes.py
│       └── exceptions.py
├── models/
│   └── .gitkeep              # Model added after training
├── tests/
│   ├── unit/
│   └── integration/
├── scripts/
│   ├── train.py
│   └── evaluate.py
├── pyproject.toml
└── README.md
```

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

**Runtime:**

- neologdn (Japanese text normalization)
- sklearn-crfsuite (CRF implementation)
- pydantic (data validation, optional but recommended)
- regex (better Unicode support than re)

**Training:**

- scikit-learn (metrics, cross-validation)

**Development:**

- Linting, type checking, and testing tools per implementer's choice (configured per Section 11)

---

## 13. Open Questions for Implementation

1. **Encoding detection library:** chardet vs charset-normalizer vs cchardet — evaluate for Japanese accuracy and speed.

2. **CRF library:** sklearn-crfsuite is the obvious choice, but verify Python 3.13 compatibility.

3. **neologdn options:** Evaluate whether to use `neologdn.normalize()` with default settings or customize (e.g., `repeat` parameter for controlling repeated character reduction).

4. **Pattern database format:** Decide between compiled regex objects vs pattern strings compiled at load time.

5. **Feature normalization:** Whether to apply standardization to numeric features before CRF training.

6. **Model versioning:** Strategy for model file naming and backward compatibility.

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
| SEPARATOR → BODY      | Medium                          |
| SEPARATOR → SIGNATURE | Medium                          |

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
