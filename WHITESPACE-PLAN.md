# Whitespace Handling Overhaul

## Executive Summary

Blank lines create an information bottleneck in the CRF. This document proposes replacing the current piecemeal workarounds with a unified architecture where **blank lines are invisible to the ML layer**.

---

## Problem Analysis

### The CRF Context Erasure Problem

A linear-chain CRF models `P(y_i | y_{i-1}, x)` — each label depends only on the immediately preceding label and current features. Blank lines act as a membrane that erases memory of what came before.

**Example failure:**
```
SIGNATURE  ★---------------------★
SIGNATURE  【添付ファイルについて】
SIGNATURE  ★---------------------★
           (blank)               ← context erased here
CLOSING    よろしくお願いいたします   ← WRONG: CLOSING after SIGNATURE
```

### Why Blank Lines Fail

1. **No meaningful emission signal:** Blank lines have no words, patterns, or character composition — just `is_blank=True` and position features.

2. **Diffuse transition probabilities:** Blank lines legitimately appear between many label pairs (GREETING→BODY, BODY→BODY, BODY→SIGNATURE, etc.), so learned transitions through blank lines are necessarily non-informative.

3. **First-order Markov limitation:** When the sequence passes through a blank line, the model forgets what came before — it cannot encode "we were in SIGNATURE territory before the blank."

### Current Workarounds (Accumulated Technical Debt)

The codebase has accumulated several workarounds related to blank line handling:

| Location | Workaround | Purpose | Status |
|----------|------------|---------|--------|
| `features.py:79-82` | Look-ahead features (`has_name_pattern_below`, etc.) | Proxy for "signature territory detection" | Implemented (PROPOSAL.md Phase 1) |
| `features.py:408-445` | `_compute_lookahead_features()` | Compute look-ahead flags | Implemented (PROPOSAL.md Phase 1) |
| `crf.py:131-133` | Look-ahead CRF features | Pass look-ahead to model | Implemented (PROPOSAL.md Phase 1) |
| `features.py:373-377` | `context_blank_count` | Count blanks in ±2 window | Pre-existing |
| `assembler.py:220-222` | Buffer OTHER lines | Include blank lines only if followed by content | Pre-existing |
| `evaluate.py:78-83` | `normalize_whitespace()` | Strip blanks for content comparison | Pre-existing |

PROPOSAL.md Phase 1 (look-ahead features) has been implemented and is reflected in current metrics (98.58% content match, 0.00% confident wrong). This plan supersedes PROPOSAL.md with a more fundamental architectural change. **The PROPOSAL.md changes must be reverted first** before implementing this plan.

**Note:** The normalizer's CHOONPU handling and dash unification are unrelated — they preserve delimiter line patterns (like `---`), not blank line handling.

---

## Architecture: Blank Lines Invisible to ML

### Core Principle

The CRF operates only on content lines. Blank lines are stripped before ML and reinserted after.

### Two Independent Concerns

1. **Feature generation:** Content lines carry features derived from adjacent whitespace. This informs labeling (e.g., "preceded by blank line" can signal section boundary).

2. **Document reconstruction:** After labeling, the original document (with all its whitespace) must be recoverable. This requires storing whitespace positions/counts separately.

**Critical:** These must remain decoupled. Feature data describes whitespace for ML purposes. Reconstruction data stores exact positions for output purposes. They share underlying information but serve different purposes and should have independent representations.

---

## Data Structures

### ContentLine (for ML pipeline)

```python
@dataclass(frozen=True, slots=True)
class ContentLine:
    """A non-blank line with whitespace context."""

    text: str
    original_index: int          # Position in original document

    # Whitespace context (for features)
    blank_lines_before: int      # Count of blank lines immediately before
    blank_lines_after: int       # Count of blank lines immediately after

    # Inherited from current AnnotatedLine
    quote_depth: int
    is_forward_reply_header: bool
    preceded_by_delimiter: bool  # Delimiter counts as content, not blank
    is_delimiter: bool
```

### WhitespaceMap (for reconstruction)

```python
@dataclass(frozen=True, slots=True)
class WhitespaceMap:
    """Mapping from content line indices to original line indices."""

    # content_index -> original_index (for labeled content lines)
    content_to_original: tuple[int, ...]

    # original_index -> True if blank (for reconstruction)
    blank_positions: frozenset[int]

    # Original line count
    original_line_count: int
```

### LineFeatures Updates

```python
@dataclass(frozen=True, slots=True)
class LineFeatures:
    # REMOVE: is_blank (always False for content lines)

    # ADD: whitespace context features
    blank_lines_before: int
    blank_lines_after: int

    # KEEP: All existing content/pattern features
    # These now only apply to content lines
```

---

## Pipeline Changes

### Current Pipeline

```
Email Text
    │
    ▼
Normalizer ──────────────────► NormalizedEmail(lines: all lines)
    │
    ▼
StructuralAnalyzer ──────────► StructuralAnalysis(lines: all lines)
    │
    ▼
FeatureExtractor ────────────► ExtractedFeatures(features: all lines)
    │
    ▼
CRFSequenceLabeler ──────────► SequenceLabelingResult(labels: all lines)
    │
    ▼
BodyAssembler (buffers blanks)► AssembledBody
```

### Proposed Pipeline

```
Email Text
    │
    ▼
Normalizer ──────────────────► NormalizedEmail(lines: all lines)
    │                              - Whitespace-only lines normalized to empty
    │
    ▼
ContentFilter ───────────────► FilteredContent(
    │                              content_lines: content only
    │                              whitespace_map: for reconstruction
    │                          )
    │
    ▼
StructuralAnalyzer ──────────► StructuralAnalysis(lines: content only)
    │
    ▼
FeatureExtractor ────────────► ExtractedFeatures(features: content only)
    │                              - NEW: blank_lines_before/after
    │                              - Position = content line index
    │
    ▼
CRFSequenceLabeler ──────────► SequenceLabelingResult(labels: content only)
    │                              - Blank lines not labeled (not seen)
    │
    ▼
Reconstructor ───────────────► ReconstructedDocument
    │                              - Blank lines reinserted (unlabeled)
    │
    ▼
BodyAssembler ───────────────► AssembledBody
```

### New Components

#### ContentFilter

```python
class ContentFilter:
    """Separates content lines from blank lines."""

    def filter(self, normalized: NormalizedEmail) -> FilteredContent:
        """Extract content lines and build whitespace map.

        Content lines: non-empty after stripping whitespace
        Blank lines: empty or whitespace-only (normalized to empty)
        """
        content_lines: list[ContentLine] = []
        blank_positions: set[int] = set()
        content_to_original: list[int] = []

        # First pass: identify content vs blank
        pending_blanks = 0

        for orig_idx, text in enumerate(normalized.lines):
            if text.strip():
                # Content line
                content_lines.append(ContentLine(
                    text=text,
                    original_index=orig_idx,
                    blank_lines_before=pending_blanks,
                    blank_lines_after=0,  # Set in second pass
                    ...
                ))
                content_to_original.append(orig_idx)
                pending_blanks = 0
            else:
                # Blank line (empty or whitespace-only)
                blank_positions.add(orig_idx)
                pending_blanks += 1

        # Second pass: set blank_lines_after for each content line
        for i in range(len(content_lines) - 1):
            curr_orig = content_lines[i].original_index
            next_orig = content_lines[i + 1].original_index
            blanks_between = next_orig - curr_orig - 1
            content_lines[i] = replace(content_lines[i], blank_lines_after=blanks_between)

        # Last content line: count trailing blanks
        if content_lines:
            last_orig = content_lines[-1].original_index
            trailing_blanks = len(normalized.lines) - last_orig - 1
            content_lines[-1] = replace(content_lines[-1], blank_lines_after=trailing_blanks)

        return FilteredContent(
            content_lines=tuple(content_lines),
            whitespace_map=WhitespaceMap(
                content_to_original=tuple(content_to_original),
                blank_positions=frozenset(blank_positions),
                original_line_count=len(normalized.lines),
            ),
        )
```

#### Reconstructor

```python
@dataclass(frozen=True, slots=True)
class ReconstructedLine:
    """A line in the reconstructed document."""

    text: str
    original_index: int
    is_blank: bool

    # Only set for content lines (is_blank=False)
    label: str | None
    confidence: float | None
    label_probabilities: dict[str, float] | None


class Reconstructor:
    """Reconstructs full document from content-only labels."""

    def reconstruct(
        self,
        labeling: SequenceLabelingResult,
        whitespace_map: WhitespaceMap,
        original_lines: tuple[str, ...],
    ) -> tuple[ReconstructedLine, ...]:
        """Reinsert blank lines into labeled sequence.

        Blank lines are marked as is_blank=True with no label.
        Content lines carry their CRF-assigned labels.
        """
        result: list[ReconstructedLine] = []
        content_idx = 0

        for orig_idx in range(whitespace_map.original_line_count):
            if orig_idx in whitespace_map.blank_positions:
                # Blank line - no label
                result.append(ReconstructedLine(
                    text=original_lines[orig_idx],
                    original_index=orig_idx,
                    is_blank=True,
                    label=None,
                    confidence=None,
                    label_probabilities=None,
                ))
            else:
                # Content line - use CRF result
                labeled = labeling.labeled_lines[content_idx]
                result.append(ReconstructedLine(
                    text=labeled.text,
                    original_index=orig_idx,
                    is_blank=False,
                    label=labeled.label,
                    confidence=labeled.confidence,
                    label_probabilities=labeled.label_probabilities,
                ))
                content_idx += 1

        return tuple(result)
```

---

## Training Changes

### Training Data Processing

Training data comes from yasumail with labels for ALL lines. The training script must:

1. Filter to content lines only (skip blank lines entirely)
2. Extract labels only for content lines
3. Compute whitespace context features
4. Train CRF on content-only sequences

```python
# In train.py

def prepare_training_example(example: dict) -> tuple[
    list[str],             # Content line texts
    list[Label],           # Labels for content lines only
    list[int],             # blank_lines_before for each content line
    list[int],             # blank_lines_after for each content line
]:
    """Convert full example to content-only training data."""
    lines_data = example["lines"]

    content_texts = []
    content_labels = []
    blanks_before = []
    blanks_after = []

    pending_blanks = 0

    for item in lines_data:
        if item["text"].strip():  # Content line
            content_texts.append(item["text"])
            content_labels.append(item["label"])
            blanks_before.append(pending_blanks)
            pending_blanks = 0
        else:
            # Blank line - skip, but count it
            pending_blanks += 1

    # Compute blanks_after (similar logic to ContentFilter)
    # ...

    return content_texts, content_labels, blanks_before, blanks_after
```

### Label Scheme

| Label | Description | In Training Data? | Status |
|-------|-------------|-------------------|--------|
| GREETING | Opening formulas | Yes | Keep |
| BODY | Substantive content | Yes | Keep |
| CLOSING | Closing formulas | Yes | Keep |
| SIGNATURE | Signature block lines | Yes | Keep |
| QUOTE | Quoted content | Yes | Keep |
| OTHER | Blank lines, noise, misc | Yes (for non-blank misc) | Keep for misc content |
| SEPARATOR | Visual dividers | **No** (not in yasumail) | Remove from scheme |

**Key insight:** The CRF will still see OTHER labels for non-blank miscellaneous content lines. Blank lines are simply not in the training data — they have no label because the model never sees them.

---

## Migration Plan

### Phase 0: Revert PROPOSAL.md Changes

**Goal:** Back out the look-ahead features added in PROPOSAL.md Phase 1.

These changes are superseded by this plan's architecture. They must be removed to establish a clean baseline.

**Files to modify:**

1. `src/yomail/pipeline/features.py`:
   - Remove from `LineFeatures` dataclass:
     - `has_name_pattern_below: bool`
     - `has_contact_info_below: bool`
     - `has_closing_pattern_below: bool`
   - Remove `_compute_lookahead_features()` method
   - Remove call to `_compute_lookahead_features()` in `_extract_line_features()`
   - Remove lookahead assignments in `_extract_line_features()` return

2. `src/yomail/pipeline/crf.py`:
   - Remove from `_features_to_dict()`:
     - `feat["has_name_below"]`
     - `feat["has_contact_below"]`
     - `feat["has_closing_below"]`

3. `tests/test_crf.py`:
   - Remove from `_make_line_features()` helper:
     - `has_name_pattern_below`
     - `has_contact_info_below`
     - `has_closing_pattern_below`

4. `tests/test_features.py`:
   - Remove look-ahead feature tests (6 tests added for PROPOSAL.md)

**After revert:**
- Run full test suite to verify baseline functionality
- Note: Model will need retraining without look-ahead features (or use pre-PROPOSAL.md model if available)

---

### Phase 1: Audit and Mark

**Goal:** Identify all blank-line-related code for removal/modification.

1. Mark current workarounds with `# WHITESPACE-OVERHAUL: remove` comments
2. Identify test changes needed
3. Document behavioral differences

**Files to audit:**
- `normalizer.py` — add normalization of whitespace-only lines to empty
- `structural.py` — update to work with content-only input
- `features.py` — remove `is_blank`, add `blank_lines_before/after`, update position to use content indices
- `crf.py` — remove `char_type=blank` bucket, update position features
- `assembler.py` — simplify (blanks already filtered out before it runs)
- `evaluate.py` — update `normalize_whitespace`, `get_expected_body`
- `train.py` — filter to content lines only

### Phase 2: New Components

**Goal:** Implement ContentFilter and Reconstructor.

1. Create `src/yomail/pipeline/content_filter.py`
   - `ContentFilter` class
   - `FilteredContent` dataclass
   - `ContentLine` dataclass
   - `WhitespaceMap` dataclass

2. Create `src/yomail/pipeline/reconstructor.py`
   - `Reconstructor` class
   - `ReconstructedLine` dataclass

3. Tests for both

### Phase 3: Feature Extractor

**Goal:** Update features for content-only operation.

1. Add `blank_lines_before`, `blank_lines_after` features
2. Remove `is_blank` feature (always False now)
3. Update position features to use content line indices
4. Update contextual features (window is now content-only)
5. Update CRF feature conversion

### Phase 4: Pipeline Integration

**Goal:** Wire new components into extractor.

1. Update `EmailBodyExtractor` pipeline:
   ```python
   normalized = self._normalizer.normalize(email_text)
   filtered = self._content_filter.filter(normalized)
   structural = self._structural_analyzer.analyze(filtered)
   features = self._feature_extractor.extract(structural)
   labeling = self._crf_labeler.predict(features, filtered.content_texts)
   reconstructed = self._reconstructor.reconstruct(
       labeling, filtered.whitespace_map, normalized.lines
   )
   assembled = self._body_assembler.assemble(reconstructed)
   ```

2. Update StructuralAnalyzer to work with FilteredContent
3. Update BodyAssembler to work with ReconstructedLine
4. Update public API types if needed
5. Update tests

### Phase 5: Training

**Goal:** Retrain model on content-only data.

1. Update `train.py` to filter content lines and compute whitespace features
2. Train new model
3. Evaluate on test set

### Phase 6: Cleanup

**Goal:** Remove deprecated code and simplify.

1. Remove marked workarounds
2. Remove SEPARATOR from label scheme (not in training data)
3. Simplify assembler (no blank line buffering needed)
4. Update documentation

---

## Test Strategy

### Existing Tests to Preserve

Most existing tests validate behavior at boundaries (greeting detection, signature patterns, etc.). These should continue to pass after the refactor.

### New Tests Needed

1. **ContentFilter tests:**
   - Correctly identifies blank vs content lines
   - Whitespace-only lines treated as blank
   - Whitespace context counts (`blank_lines_before/after`) are accurate
   - Edge cases: all blank, no blank, leading/trailing blanks

2. **Reconstructor tests:**
   - Round-trip: filter then reconstruct preserves line count and order
   - Blank lines have `is_blank=True` and no label
   - Content lines have their CRF-assigned labels

3. **Feature tests:**
   - `blank_lines_before/after` computed correctly
   - Contextual window operates on content lines only
   - Position features use content indices

4. **Integration tests:**
   - Full pipeline produces correct output
   - Body extraction works correctly with blank lines present

### Regression Metrics

Before/after comparison on test set:
- Content match rate (primary)
- Confident wrong rate (critical — should decrease)
- Per-label F1 (especially CLOSING, SIGNATURE)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Worse accuracy after retrain | Medium | High | Keep old model as fallback; A/B test |
| Feature engineering oversights | Low | Medium | Comprehensive test suite |
| Position features break | Medium | Medium | Use content line indices consistently |
| Training data mismatch | Low | High | Careful handling of blank line filtering |

### Rollback Plan

This work is on a branch (`whitespace-overhaul`). If results are worse:
1. Do not merge
2. Document findings
3. Consider hybrid approaches from PROPOSAL.md

---

## Success Criteria

Baseline for comparison is **pre-PROPOSAL.md** (after Phase 0 revert):
- Content match: 97.97%
- Confident wrong: 4 (0.41%)

Target metrics:

1. **Confident wrong rate < 0.1%** (improve from 0.41%)
2. **Content match rate >= 98.0%** (improve from 97.97%)
3. **No CLOSING-after-SIGNATURE errors** (the specific failure mode this addresses)
4. **Cleaner codebase** — fewer special cases, unified blank line handling

Note: Current metrics (98.58% / 0.00%) include PROPOSAL.md look-ahead features which will be removed. Success means achieving similar or better results through the cleaner architecture.

---

## Resolved Design Decisions

1. **Delimiter lines (---) are content, not blank.**
   They have semantic meaning (section separators) and pattern features.

2. **Whitespace-only lines are normalized to empty, then treated as blank.**
   Lines containing only spaces/tabs have no semantic content.

3. **SEPARATOR label will be removed.**
   It's not in the yasumail training data. Visual delimiters are content lines with appropriate labels (often OTHER or SIGNATURE depending on context).

4. **Position features use content line indices.**
   The model sees content lines only, so positions should reflect what the model sees.

5. **Blank lines have no label.**
   They are not seen by ML and therefore not labeled. The `ReconstructedLine` struct has `label=None` for blank lines.

---

## Summary

This plan replaces accumulated blank line workarounds with a clean architecture:

- **Blank lines are invisible to ML** — not in sequences, no labels, no features
- **Whitespace context as features** — content lines carry `blank_lines_before/after`
- **Clean reconstruction** — blank lines reinserted with `is_blank=True`, no synthetic labels

The result is a simpler, more principled system that directly addresses the CRF context erasure problem by removing the context-erasing elements from the sequence entirely.
