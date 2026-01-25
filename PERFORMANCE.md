# PERFORMANCE.md — yomail

Current model performance metrics. Last evaluated: 2026-01-25.

## Summary

| Metric              | Value   | Target   | Status |
|---------------------|---------|----------|--------|
| Content match rate  | 97.91%  | 99.99%   | Below  |
| Acceptable rate     | 97.96%  | -        | -      |
| Confident wrong     | 0.14%   | <0.1%    | Above  |
| Model size          | 12 KB   | <10 MB   | OK     |

## Evaluation Details

**Test set:** 19,642 examples (yasumail synthetic data, seed=999, noise=0.2)
**Model:** models/email_body.crfsuite (trained on 4,911 examples)

### Primary Metrics

| Metric             | Count  | Rate    |
|--------------------|--------|---------|
| Total examples     | 19,642 | 100%    |
| Content match      | 19,231 | 97.91%  |
| Exact match        | 19,231 | 97.91%  |
| Acceptable         | 19,242 | 97.96%  |

### Failure Analysis

| Category          | Count | Rate   | Description                      |
|-------------------|-------|--------|----------------------------------|
| Failed static     | 384   | 1.96%  | Correctly rejected (acceptable)  |
| Confident wrong   | 27    | 0.14%  | Wrong result returned (dangerous)|

**Note:** Failed static includes emails correctly rejected due to low confidence or no body detected. These are acceptable failures. Confident wrong is the critical metric — these are errors that slip through.

### Confidence Distribution

| Statistic | Value |
|-----------|-------|
| Mean      | 0.913 |
| Median    | 0.963 |
| Min       | 0.500 |
| Max       | 1.000 |
| P10       | 0.740 |
| P90       | 0.992 |

### Error Breakdown

| Error Type          | Count |
|---------------------|-------|
| LowConfidenceError  | 382   |
| NoBodyDetectedError | 2     |

### Per-Label Metrics

| Label    | Precision | Recall | F1    |
|----------|-----------|--------|-------|
| GREETING | 0.333     | 1.000  | 0.500 |
| BODY     | 1.000     | 0.968  | 0.984 |
| CLOSING  | 0.300     | 1.000  | 0.462 |

**Note:** Low precision for GREETING and CLOSING is expected — these labels appear infrequently and the model tends to over-predict them near document boundaries. This doesn't significantly impact body extraction since GREETING and CLOSING are included in the body.

### Failures by Template Type

**Confident Wrong (27 total):**

| Template Type   | Count |
|-----------------|-------|
| informal        | 10    |
| formal_full     | 8     |
| mobile_reply    | 6     |
| formal_minimal  | 2     |
| inline_reply    | 1     |

**All Failures (411 total):**

| Template Type   | Count |
|-----------------|-------|
| formal_full     | 184   |
| informal        | 102   |
| inline_reply    | 52    |
| formal_minimal  | 38    |
| mobile_reply    | 34    |
| ultraminimal    | 1     |

## Known Issues

1. **Informal emails** account for 37% of confident-wrong failures (10/27). Short, casual content is harder to distinguish from signatures.

2. **formal_full** has the most total failures (184) due to its frequency in the test set, but only 8 confident-wrong (4.3% of that category).

3. **inline_reply** has 52 total failures but only 1 confident-wrong, meaning the model correctly rejects complex interleaved replies it can't handle.

## Historical Progress

| Date       | Content Match | Confident Wrong | Notes                              |
|------------|---------------|-----------------|-------------------------------------|
| 2026-01-24 | 73.8%         | 64 (6.4%)       | Initial evaluation                  |
| 2026-01-25 | 88.8%         | 57              | Assembler fix (OTHER as neutral)    |
| 2026-01-25 | 90.5%         | 58              | Dash unification                    |
| 2026-01-25 | 96.8%         | 9               | CHOONPU preservation                |
| 2026-01-25 | 98.2%         | 7               | forward_only filtering              |
| 2026-01-25 | 97.97%        | 4               | Name detection feature              |
| 2026-01-25 | 98.48%        | 3               | Look-ahead features                 |
| 2026-01-25 | 98.58%        | 0               | Closing pattern fixes               |
| 2026-01-25 | 97.91%        | 27 (0.14%)      | Current (larger test set: 19,642)   |

**Note:** Performance was measured on different test set sizes over time. The current evaluation uses a larger 19,642-example test set, which explains some apparent regression from earlier metrics.

## Resource Usage

| Resource         | Value   | Target    | Status |
|------------------|---------|-----------|--------|
| Model file size  | 12 KB   | < 10 MB   | OK     |
| Package size     | ~1 MB   | < 20 MB   | OK     |
| Inference latency| ~10-30ms| < 500 ms  | OK     |

## Improvement Opportunities

1. **Reduce confident-wrong rate** — Currently 0.14% vs 0.1% target
   - Focus on informal templates (10 of 27 failures)
   - Consider additional features for short, casual content

2. **Improve CLOSING/GREETING precision** — Low precision doesn't hurt body extraction but indicates over-prediction that could be tightened

3. **inline_reply handling** — 52 failures but most correctly rejected; could improve coverage with more training data

## Commands

```bash
# Evaluate on test set
.venv/bin/python scripts/evaluate.py data/test.jsonl

# Evaluate with verbose failure output
.venv/bin/python scripts/evaluate.py data/test.jsonl --verbose

# Evaluate subset
.venv/bin/python scripts/evaluate.py data/test.jsonl -n 1000

# Analyze specific failures
.venv/bin/python scripts/dump_failures.py data/test.jsonl -n 10
```
