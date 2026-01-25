# Proposal: Addressing the OTHER Context Erasure Problem

## Problem Statement

The CRF model incorrectly predicts CLOSING after SIGNATURE in some emails:

```
SIGNATURE  ★---------------------★
SIGNATURE  【添付ファイルについて】
...
SIGNATURE  ★---------------------★
OTHER      (blank)               ← context erased here
CLOSING    よろしくお願いいたします.   ← wrong! CLOSING after SIGNATURE
OTHER      (blank)
SIGNATURE  新井辰夫
```

This violates the expected email structure where CLOSING precedes SIGNATURE.

## Root Cause Analysis

### Linear-Chain CRF Limitation

A linear-chain CRF models `P(y_i | y_{i-1}, x)` - each label depends only on the **previous** label and current features. It cannot encode global constraints like "CLOSING must precede all SIGNATURE lines."

### OTHER as a "Reset State"

The OTHER label (used for blank lines) connects to almost everything:
- `OTHER → CLOSING`: 4320 occurrences in training
- `OTHER → SIGNATURE`: common
- `OTHER → BODY`: common

When the model transitions through OTHER, it "forgets" what came before:

```
SIGNATURE → OTHER → CLOSING
            ↑
            context erased
```

The model sees `OTHER → CLOSING` as valid (it's common!) without knowing we were just in a SIGNATURE block.

### Why We Keep OTHER

Blank lines serve as **boundaries**, not content. We can't simply label them as BODY or SIGNATURE because:

1. They're not content - labeling them SIGNATURE is semantically wrong
2. They preserve original formatting in extracted output
3. They carry structural signal (paragraph breaks vs section breaks)

Labeling blanks based on context creates a chicken-and-egg problem: we'd need to know surrounding labels to assign the blank's label, but we're trying to predict those labels.

## Proposed Solutions

### Solution A: Look-Ahead Proxy Features

Add features that approximate "are we in signature territory?" without requiring predicted labels.

**New features:**
```python
# For each line, compute:
has_name_pattern_below: bool      # Any name patterns in lines below?
has_contact_info_below: bool      # Contact info patterns below?
has_signature_pattern_below: bool # Company/position patterns below?
lines_to_next_name: int           # Distance to next name pattern (-1 if none)
```

**Rationale:** These features let the model know "signature content is coming" which helps it:
- Not predict CLOSING when signature patterns are below
- Understand that a blank line near signature content is transitional, not a reset

**Pros:**
- Pure feature engineering, no model changes
- Computable at feature extraction time (no chicken-egg)
- Semantically clean - OTHER stays OTHER

**Cons:**
- Relies on pattern detection quality
- Adds feature computation cost (minor)
- May not fully solve the problem

### Solution B: Flexible Training Labels for OTHER

Allow certain label substitutions during training without penalty.

**Concept:** When ground truth is OTHER but the line is between SIGNATURE lines, accept SIGNATURE as correct during training.

**Implementation options:**

1. **Soft labels during training:**
   ```python
   # Instead of hard labels, provide acceptable alternatives
   if ground_truth == "OTHER" and between_signatures:
       acceptable_labels = ["OTHER", "SIGNATURE"]
   ```

2. **Label smoothing for OTHER:**
   ```python
   # During training, OTHER lines get partial credit for contextual labels
   if ground_truth == "OTHER":
       # Don't penalize SIGNATURE if adjacent to SIGNATURE
       # Don't penalize BODY if adjacent to BODY
   ```

3. **Pre-process training data:**
   ```python
   # Convert OTHER to contextual labels before training
   if label == "OTHER" and prev_label == "SIGNATURE" and next_label == "SIGNATURE":
       label = "SIGNATURE"  # Relabel for training only
   ```

**Ambiguous cases to handle:**

| Context | Ground Truth | Acceptable Labels |
|---------|--------------|-------------------|
| SIGNATURE - blank - SIGNATURE | OTHER | OTHER, SIGNATURE |
| BODY - blank - BODY | OTHER | OTHER, BODY |
| CLOSING - blank - SIGNATURE | OTHER | OTHER, SIGNATURE (?) |
| BODY - blank - CLOSING | OTHER | OTHER, BODY, CLOSING (?) |

**Pros:**
- Directly addresses the context erasure by making OTHER less "resetting"
- Model learns that blank lines can inherit surrounding context
- Doesn't require inference-time changes

**Cons:**
- Complicates training pipeline
- Need to carefully define which substitutions are acceptable
- May reduce precision on actual OTHER classification
- python-crfsuite may not support soft labels natively (would need pre-processing)

### Solution C: Post-Processing Constraints

Enforce structural constraints after CRF prediction.

**Rules:**
```python
def enforce_constraints(labels):
    # Rule 1: CLOSING cannot appear after first SIGNATURE
    first_sig = first_index_of(labels, "SIGNATURE")
    if first_sig is not None:
        for i in range(first_sig + 1, len(labels)):
            if labels[i] == "CLOSING":
                labels[i] = "BODY"  # or keep as-is and flag

    # Rule 2: Re-classify isolated label runs
    # ... etc
```

**Pros:**
- Simple to implement
- Guarantees structural validity
- No training changes needed

**Cons:**
- Doesn't improve model understanding
- May paper over deeper issues
- Hard-coded rules are brittle
- Loses confidence information for corrected labels

### Solution D: Constrained Viterbi Decoding

Modify the decoding algorithm to forbid certain transitions in context.

**Concept:** During Viterbi decoding, track whether SIGNATURE has been seen and forbid CLOSING afterward.

**Pros:**
- Principled approach
- Model-integrated solution

**Cons:**
- python-crfsuite doesn't expose decoding customization
- Would need custom implementation or different library
- Adds inference complexity

## Recommendation

**Phase 1: Implement Solution A (Look-Ahead Features)**

This is the cleanest approach:
- No changes to training pipeline or labels
- Computable from patterns we already detect
- Addresses root cause by giving model forward context

**Phase 2: Evaluate and Consider Solution B**

If look-ahead features don't fully solve the problem:
- Implement training data pre-processing to relabel ambiguous OTHER lines
- Keep it simple: only relabel OTHER when surrounded by same label type

**Phase 3: Solution C as Safety Net**

Add lightweight post-processing constraints as a final safety net:
- Flag (don't auto-correct) sequences that violate structure
- Use for confidence reduction rather than label changes

## Implementation Plan

### Phase 1: Look-Ahead Features

1. Add to `LineFeatures`:
   ```python
   has_name_pattern_below: bool
   has_contact_info_below: bool
   lines_to_end: int  # Already have this as lines_from_end
   ```

2. Compute in `FeatureExtractor._extract_line_features()`:
   ```python
   # Pre-compute pattern flags for all lines (already done)
   # Then for each line, check lines below
   has_name_below = any(
       all_flags[j]["has_name_pattern"]
       for j in range(idx + 1, total_lines)
   )
   ```

3. Add to CRF features in `_features_to_dict()`:
   ```python
   feat["has_name_below"] = features.has_name_pattern_below
   feat["has_contact_below"] = features.has_contact_info_below
   ```

4. Retrain and evaluate

### Phase 2: Flexible OTHER Training (if needed)

1. Create training data preprocessor:
   ```python
   def relabel_ambiguous_other(labels):
       """Relabel OTHER lines that are surrounded by same label."""
       new_labels = list(labels)
       for i in range(1, len(labels) - 1):
           if labels[i] == "OTHER":
               if labels[i-1] == labels[i+1] and labels[i-1] != "OTHER":
                   new_labels[i] = labels[i-1]
       return tuple(new_labels)
   ```

2. Apply during training only (not evaluation)

3. Retrain and evaluate

## Open Questions

1. **Should look-ahead features include quote patterns?** Probably not - quotes can appear anywhere.

2. **How far ahead should we look?** Start with "any pattern below", could refine to "within N lines".

3. **Should we weight closer patterns more heavily?** Could add `lines_to_next_name` as numeric feature.

4. **What about CLOSING patterns below?** If we see closing patterns below, current line is probably not signature. Add `has_closing_pattern_below`?

5. **Evaluation metric:** How do we measure improvement on this specific issue vs overall accuracy?

## Success Criteria

- Confident wrong rate < 0.5% (currently 0.41%)
- No regression on content match rate (currently 97.97%)
- Specifically: Example #1 (info block before closing) correctly handled
