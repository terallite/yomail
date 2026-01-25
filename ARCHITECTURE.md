# ARCHITECTURE.md — yomail

System architecture as-built. Last updated: 2026-01-25.

## Overview

yomail extracts body text from Japanese business emails using a CRF (Conditional Random Field) sequence labeling approach. The system classifies each line of an email into one of six labels, then assembles the body from labeled lines.

**Key characteristics:**

- CRF-based ML pipeline with hand-crafted features
- Model size: 12 KB
- Inference: ~10-30ms typical
- Training: Minutes on synthetic data

## Pipeline

```
Email Text
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  NORMALIZER                                                     │
│  - Line ending normalization (CRLF/CR → LF)                     │
│  - neologdn normalization (full-width → half-width, etc.)       │
│  - NFKC Unicode normalization                                   │
│  - Zero-width character stripping                               │
│  - Delimiter line preservation (prevents CHOONPU collapse)      │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  CONTENT FILTER                                                 │
│  - Separates blank lines from content lines                     │
│  - Builds WhitespaceMap for reconstruction                      │
│  - Tracks blank_lines_before/after per content line             │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  STRUCTURAL ANALYZER                                            │
│  - Quote depth tracking (>, |)                                  │
│  - Forward/reply header detection                               │
│  - Visual delimiter detection                                   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  FEATURE EXTRACTOR                                              │
│  - Positional features (normalized, relative to quotes)         │
│  - Content features (char ratios, length)                       │
│  - Whitespace context (blank lines before/after)                │
│  - Pattern flags (greeting, closing, contact, name, etc.)       │
│  - Contextual aggregates (window ±2 lines)                      │
│  - Bracket detection (info blocks vs signatures)                │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  CRF SEQUENCE LABELER (python-crfsuite)                         │
│  - Per-line label prediction                                    │
│  - Marginal probability output                                  │
│  - Post-processing: fix impossible transitions                  │
│  - Post-processing: unify bracketed blocks                      │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  RECONSTRUCTOR                                                  │
│  - Reinserts blank lines at original positions                  │
│  - Blank lines inherit preceding content line's label           │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  BODY ASSEMBLER                                                 │
│  - Signature boundary detection                                 │
│  - Inline vs trailing/leading quote classification              │
│  - Content block building with merging logic                    │
│  - Body selection (all pre-sig or longest block)                │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  CONFIDENCE CHECK                                               │
│  - Viterbi sequence probability as confidence                   │
│  - Threshold check (default 0.5)                                │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
Extracted Body or Exception
```

## Label Scheme

| Label     | Description                                             |
| --------- | ------------------------------------------------------- |
| GREETING  | Opening formulas (お世話になっております, 拝啓, etc.)   |
| BODY      | Substantive content                                     |
| CLOSING   | Closing formulas (よろしくお願いいたします, 敬具, etc.) |
| SIGNATURE | Signature block lines                                   |
| QUOTE     | Quoted content (any depth)                              |
| OTHER     | Separators, blank lines, unclassifiable                 |

## Module Structure

```
src/yomail/
├── __init__.py              # Public exports
├── extractor.py             # EmailBodyExtractor (main API)
├── exceptions.py            # ExtractionError hierarchy
│
├── pipeline/
│   ├── __init__.py          # Pipeline exports
│   ├── normalizer.py        # Normalizer, NormalizedEmail
│   ├── content_filter.py    # ContentFilter, WhitespaceMap
│   ├── structural.py        # StructuralAnalyzer, AnnotatedLine
│   ├── features.py          # FeatureExtractor, LineFeatures
│   ├── crf.py               # CRFSequenceLabeler, CRFTrainer
│   ├── reconstructor.py     # Reconstructor, ReconstructedDocument
│   └── assembler.py         # BodyAssembler, AssembledBody
│
└── patterns/
    ├── __init__.py          # Pattern exports
    ├── greetings.py         # is_greeting_line()
    ├── closings.py          # is_closing_line()
    ├── signatures.py        # is_contact_info_line(), is_company_line(), is_position_line()
    ├── separators.py        # is_separator_line()
    └── names.py             # is_name_line(), contains_known_name()
```

## Feature Summary

Features extracted per line (35 total):

**Positional (6):**

- position_normalized, position_reverse
- lines_from_start, lines_from_end
- position_rel_first_quote, position_rel_last_quote

**Content (9):**

- line_length
- kanji_ratio, hiragana_ratio, katakana_ratio
- ascii_ratio, digit_ratio, symbol_ratio
- leading_whitespace, trailing_whitespace

**Whitespace Context (2):**

- blank_lines_before, blank_lines_after

**Structural (4):**

- quote_depth
- is_forward_reply_header
- preceded_by_delimiter, is_delimiter

**Pattern Flags (9):**

- is_greeting, is_closing
- has_contact_info, has_company_pattern, has_position_pattern
- has_name_pattern, is_visual_separator
- has_meta_discussion, is_inside_quotation_marks

**Contextual (5):**

- context_greeting_count, context_closing_count
- context_contact_count, context_quote_count, context_separator_count

**Bracket (2):**

- in_bracketed_section, bracket_has_signature_patterns

**Derived Categorical (4, CRF only):**

- BOS/EOS markers
- pos_bucket (start/early/middle/late/end)
- quote_depth_cat (quoted/unquoted)
- char_type (ascii_heavy/japanese_heavy/mixed)
- bracket_cat (bracketed/unbracketed)

## Post-Processing Rules

The CRF labeler applies two post-processing passes:

1. **Fix Impossible Transitions:**
   - SIGNATURE → CLOSING is impossible (relabel to SIGNATURE)
   - Separator lines (delimiters) cannot be CLOSING

2. **Unify Bracketed Blocks:**
   - Find blocks sandwiched by matching separators (★---★)
   - If >50% BODY → unify entire block to BODY
   - If >50% SIGNATURE → unify entire block to SIGNATURE

## Body Assembly Logic

1. **Find signature boundary:** First non-blank SIGNATURE line
2. **Classify quotes:** Inline if content exists before AND after
3. **Build content blocks:**
   - BODY, GREETING, CLOSING accumulate into current block
   - Inline QUOTE included in block
   - OTHER/blank lines buffer (neutral filler)
   - Trailing/leading QUOTE creates hard break
4. **Select body:**
   - If signature found: concatenate all blocks before it
   - If no signature: select longest block
5. **Assemble text:** Join with newlines

## Dependencies

**Runtime:**

- neologdn (Japanese text normalization)
- python-crfsuite (CRF implementation)
- pyyaml (name data loading)

**Development:**

- pytest (testing)
- ruff (linting/formatting)
- ty (type checking)

## Public API

```python
from yomail import EmailBodyExtractor

extractor = EmailBodyExtractor(model_path="models/email_body.crfsuite")

# Strict - raises on failure
body = extractor.extract(email_text)

# Safe - returns None on failure
body = extractor.extract_safe(email_text)

# Full metadata
result = extractor.extract_with_metadata(email_text)
# result.body, result.confidence, result.success, result.error
# result.labeled_lines, result.signature_detected, result.inline_quotes_included
```

## Exceptions

```
ExtractionError (base)
├── InvalidInputError    # Empty or invalid input
├── NoBodyDetectedError  # No body content found
└── LowConfidenceError   # Confidence below threshold
```

## Training Data

Generated by yasumail project:

- Format: JSONL with email_text, lines (with label per line), metadata
- Training: 4911 examples (forward_only excluded)
- Test: 19642 examples

## Design Deviations from DESIGN.md

1. **python-crfsuite over sklearn-crfsuite** — sklearn-crfsuite is unmaintained
2. **SEPARATOR label removed** — Not in training data; OTHER covers all non-content
3. **Viterbi probability as confidence** — Simpler than P10 marginals
4. **ContentFilter added** — Separates blank lines before CRF for cleaner features
5. **Reconstructor added** — Reinserts blanks after CRF for assembly
