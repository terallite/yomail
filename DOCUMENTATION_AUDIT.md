# Documentation Audit Report — yomail

**Audit Date:** 2026-01-26
**Audited By:** Claude (Opus 4.5)
**Status:** Partial remediation complete

This document lists all identified discrepancies ("drift") between the documentation and the actual codebase implementation.

## Remediation Summary

The following changes were made to address audit findings:

1. **DESIGN.md** — Added prominent disclaimer marking it as "original design specification (reference only)" and pointing to ARCHITECTURE.md for current implementation details
2. **DESIGN.md** — Stripped detailed implementation specs that are now covered by ARCHITECTURE.md
3. **DESIGN.md** — Added notes about unimplemented features (CLI, environment variables) and resolved implementation questions
4. **ARCHITECTURE.md** — Fixed feature count from 35 to 37
5. **ARCHITECTURE.md** — Added note marking it as authoritative documentation

**Remaining issues** are noted with [OPEN] or [FIXED] tags below.

---

## Executive Summary

| Severity | Original Count | Addressed | Remaining |
|----------|----------------|-----------|-----------|
| High (functional impact) | 4 | 3 | 1 |
| Medium (misleading claims) | 5 | 4 | 1 |
| Low (minor inconsistencies) | 6 | 4 | 2 |

---

## High Severity Issues

### 1. README.md Example Output is Incorrect [OPEN]

**Location:** `README.md:64-74`

**Claim:** The example shows this output:
```
お世話になっております。
山田です。

先日ご依頼いただいた資料を添付いたします。
ご確認のほどよろしくお願いいたします。

以上
```

**Evidence (actual behavior):**
```python
>>> extractor.extract_with_metadata(email_text).body
株式会社サンプル
田中様

お世話になっております。
山田です。

先日ご依頼いただいた資料を添付いたします。
ご確認のほどよろしくお願いいたします。
```

**Issues Found:**
1. The actual output includes "株式会社サンプル" and "田中様" (addressee lines), which the documentation implies would be excluded as greeting/addressing
2. The actual output is missing "以上" (closing phrase), which the documentation shows as included
3. The example email's confidence score is 0.484, which is below the default threshold of 0.5, meaning `extract()` would raise `LowConfidenceError` and `extract_safe()` would return `None`

**Impact:** Users following the README example will get different results or exceptions.

---

### 2. CLI Not Implemented [FIXED]

**Location:** `DESIGN.md:429-471`

**Resolution:** DESIGN.md section 6 now notes that CLI was not implemented.

**Claim:** DESIGN.md specifies a complete CLI with:
- `python -m yomail` command
- `--mode {strict,safe,full}` options
- `--confidence-threshold` option
- `-v, --verbose` flag
- JSON output mode

**Evidence:**
```bash
$ ls /home/user/yomail/src/yomail/__main__.py
ls: cannot access '/home/user/yomail/src/yomail/__main__.py': No such file or directory
```

**Impact:** CLI functionality documented in DESIGN.md is completely missing from the implementation.

---

### 3. Environment Variable Configuration Not Implemented [FIXED]

**Location:** `DESIGN.md:580-584`

**Resolution:** DESIGN.md section 9 now notes that environment variables were not implemented.

**Claim:** DESIGN.md states:
> Environment variables (or pass to constructor):
> - `YOMAIL_CONFIDENCE_THRESHOLD`: float, default 0.5
> - `YOMAIL_LOG_LEVEL`: DEBUG/INFO/WARNING/ERROR

**Evidence:**
```bash
$ grep -r "YOMAIL_" /home/user/yomail/src/
# No matches found
```

The extractor only accepts `confidence_threshold` as a constructor parameter, not from environment variables.

**Impact:** Users cannot configure the library via environment variables as documented.

---

### 4. patterns/quotes.py Missing [FIXED]

**Location:** `DESIGN.md:612-615`

**Resolution:** DESIGN.md section 10 now documents the actual module structure and notes differences from original design.

**Claim:** The project structure shows:
```
patterns/
├── greetings.py
├── closings.py
├── signatures.py
└── quotes.py      # <-- Documented
```

**Evidence:**
```bash
$ ls /home/user/yomail/src/yomail/patterns/
__init__.py  closings.py  greetings.py  names.py  separators.py  signatures.py
# No quotes.py file
```

Note: Quote handling is embedded in `structural.py` instead of a dedicated `quotes.py` file.

**Impact:** Module structure differs from documented design. The `names.py` and `separators.py` files exist but aren't shown in DESIGN.md structure.

---

## Medium Severity Issues

### 5. Feature Count Mismatch [FIXED]

**Location:** `ARCHITECTURE.md:134`

**Resolution:** ARCHITECTURE.md now correctly states 37 features.

**Claim:** "Features extracted per line (35 total)"

**Evidence:**
```python
>>> from yomail.pipeline.features import LineFeatures
>>> from dataclasses import fields
>>> len(fields(LineFeatures))
37
```

The actual `LineFeatures` dataclass has 37 fields, not 35. The additional features are:
- `in_bracketed_section` (documented under "Bracket (2)")
- `bracket_has_signature_patterns` (documented under "Bracket (2)")

The ARCHITECTURE.md lists these two bracket features but the total count (35) doesn't include them.

**Impact:** Minor documentation inaccuracy; the features themselves are documented, just the count is wrong.

---

### 6. Model Size Contradiction Between Documents [FIXED]

**Location:** `DESIGN.md:107` vs `ARCHITECTURE.md:12`, `README.md:11`

**Resolution:** DESIGN.md section 13 now documents that model size is 12KB (resolved implementation question).

**Claims:**
- DESIGN.md says: "Memory: Model ~5MB"
- ARCHITECTURE.md says: "Model size: 12 KB"
- README.md says: "Small model size (12 KB)"

**Evidence:**
```bash
$ ls -la /home/user/yomail/src/yomail/data/email_body.crfsuite
-rw-r--r-- 1 root root 12472 Jan 26 03:01 ...
```

The actual model is 12 KB. DESIGN.md's "~5MB" is inaccurate.

**Impact:** DESIGN.md has outdated/incorrect model size estimate.

---

### 7. Dependency Discrepancy [FIXED]

**Location:** `DESIGN.md:662-669` vs `pyproject.toml`

**Resolution:** DESIGN.md section 12 now documents original vs actual dependencies.

**Claim:** DESIGN.md lists runtime dependencies:
- neologdn
- sklearn-crfsuite
- pydantic (recommended)
- regex

**Evidence (pyproject.toml:23-27):**
```toml
dependencies = [
    "neologdn>=0.5.6",
    "python-crfsuite>=0.9.12",
    "pyyaml>=6.0",
]
```

**Issues:**
1. Uses `python-crfsuite` instead of `sklearn-crfsuite` (ARCHITECTURE.md notes this as intentional deviation)
2. `pydantic` is not used
3. `regex` is not used (standard `re` module is used instead)
4. `pyyaml` is used but not mentioned in DESIGN.md

**Impact:** Dependency list in DESIGN.md doesn't match actual implementation.

---

### 8. Performance Metrics Inconsistency [OPEN]

**Location:** `README.md:105-108` vs `PERFORMANCE.md:9-11`

**Claims:**
- README.md: "Acceptable rate: 98.0%"
- PERFORMANCE.md: "Acceptable rate: 97.96%"

**Evidence:** PERFORMANCE.md has the precise figure (97.96%), while README.md rounds to 98.0%.

**Impact:** Minor inconsistency between documents; both are approximately correct.

---

### 9. CRF Library Discrepancy (Documented Deviation) [FIXED]

**Location:** `DESIGN.md:239` vs `ARCHITECTURE.md:261`

**Resolution:** DESIGN.md section 12 now explicitly documents that python-crfsuite is used instead of sklearn-crfsuite.

**Claim:** DESIGN.md says "Uses sklearn-crfsuite or equivalent"

**Evidence:** ARCHITECTURE.md documents this as an intentional deviation:
> "python-crfsuite over sklearn-crfsuite — sklearn-crfsuite is unmaintained"

**Impact:** None (properly documented as deviation in ARCHITECTURE.md), but DESIGN.md should be updated.

---

## Low Severity Issues

### 10. Training Data Output Path in README [OPEN]

**Location:** `README.md:153`

**Claim:** Training command shows:
```bash
python scripts/train.py data/training.jsonl -o models/email_body.crfsuite
```

**Evidence:** The bundled model is actually at:
```
src/yomail/data/email_body.crfsuite
```

The `models/` directory exists but is empty (contains only `.gitkeep`). The bundled model path is different from the training output path example.

**Impact:** Confusion about where models are stored.

---

### 11. Missing ContentFilter and Reconstructor in DESIGN.md Pipeline [FIXED]

**Location:** `DESIGN.md:39-95`

**Resolution:** DESIGN.md section 3 now points to ARCHITECTURE.md and lists the actual pipeline stages including ContentFilter and Reconstructor.

**Claim:** DESIGN.md shows this pipeline:
1. NORMALIZER
2. STRUCTURAL ANALYZER
3. FEATURE EXTRACTOR
4. CRF SEQUENCE LABELER
5. BODY ASSEMBLER
6. CONFIDENCE GATE

**Evidence (ARCHITECTURE.md:18-91 and extractor.py):** Actual pipeline:
1. NORMALIZER
2. **CONTENT FILTER** (not in DESIGN.md)
3. STRUCTURAL ANALYZER
4. FEATURE EXTRACTOR
5. CRF SEQUENCE LABELER
6. **RECONSTRUCTOR** (not in DESIGN.md)
7. BODY ASSEMBLER
8. CONFIDENCE CHECK

ARCHITECTURE.md documents these additions in the "Design Deviations from DESIGN.md" section.

**Impact:** DESIGN.md pipeline is incomplete; deviations are documented in ARCHITECTURE.md.

---

### 12. Confidence Computation Method [FIXED]

**Location:** `DESIGN.md:280-284` vs actual implementation

**Resolution:** DESIGN.md section 3 now defers to ARCHITECTURE.md which correctly documents Viterbi probability as confidence.

**Claim:** DESIGN.md states confidence is computed as:
> "Base confidence: 10th percentile (P10) of marginal probabilities among body-labeled lines"

**Evidence (extractor.py:216):**
```python
# Step 6: Confidence is the Viterbi sequence probability
confidence = labeling.sequence_probability
```

ARCHITECTURE.md documents this as an intentional deviation:
> "Viterbi probability as confidence — Simpler than P10 marginals"

**Impact:** DESIGN.md describes a different confidence computation method than what's implemented.

---

### 13. Package Size Claim [OPEN]

**Location:** `PERFORMANCE.md:117`

**Claim:** "Package size: ~1 MB"

**Evidence:** The `names.yaml` file alone is ~704 KB. With the model file (12 KB) and source code, the installed package is likely larger than 1 MB, though still well under the 20 MB target.

**Impact:** Minor inaccuracy; would need actual wheel build to verify precisely.

---

### 14. Test Directory Structure [FIXED]

**Location:** `DESIGN.md:617-619`

**Resolution:** DESIGN.md section 10 now notes that test structure differs from original design.

**Claim:** Test directory structure shows:
```
tests/
├── unit/
└── integration/
```

**Evidence:**
```bash
$ ls /home/user/yomail/tests/
test_assembler.py  test_content_filter.py  test_crf.py  test_extractor.py
test_features.py   test_names.py  test_normalizer.py  test_reconstructor.py
test_structural.py
```

Tests are flat, not organized into `unit/` and `integration/` subdirectories.

**Impact:** Minor structural difference from design spec.

---

### 15. Missing `yomail[train]` Optional Dependencies [FIXED]

**Location:** `DESIGN.md:555-558`

**Resolution:** DESIGN.md section 9 now removes mention of `yomail[train]` and documents actual installation.

**Claim:**
```
pip install yomail[train]
```

**Evidence (pyproject.toml):** No `[project.optional-dependencies]` section defining training extras. Only dev dependencies are defined in `[dependency-groups]`.

**Impact:** The `yomail[train]` installation option doesn't exist.

---

## Summary of Required Fixes

### Remaining Issues (4 total)

**Critical:**
1. [OPEN] Update README.md example with realistic output or add disclaimer about confidence threshold

**Low Priority:**
2. [OPEN] Align performance metrics precisely between README and PERFORMANCE.md (98.0% vs 97.96%)
3. [OPEN] Add note about bundled model location in README vs training output path
4. [OPEN] Verify and update package size claim in PERFORMANCE.md

### Addressed Issues (11 total)

The following have been addressed by updating DESIGN.md and ARCHITECTURE.md:

- ✅ CLI documentation (marked as not implemented)
- ✅ Environment variable configuration (marked as not implemented)
- ✅ Module structure documentation
- ✅ Feature count (corrected to 37)
- ✅ Model size documentation
- ✅ Dependency documentation
- ✅ CRF library documentation
- ✅ Pipeline stage documentation
- ✅ Confidence computation documentation
- ✅ Test directory structure documentation
- ✅ Training extras (`yomail[train]`) documentation

---

## Verification Commands

To verify these findings:

```bash
# 1. Test README example
uv run python3 -c "
from yomail import EmailBodyExtractor
extractor = EmailBodyExtractor()
email = '''株式会社サンプル
田中様

お世話になっております。
山田です。

先日ご依頼いただいた資料を添付いたします。
ご確認のほどよろしくお願いいたします。

以上

--
山田太郎
株式会社テスト
TEL: 03-1234-5678'''
result = extractor.extract_with_metadata(email)
print('Body:', repr(result.body))
print('Confidence:', result.confidence)
print('Would fail with default threshold:', result.confidence < 0.5)
"

# 2. Verify CLI missing
ls /home/user/yomail/src/yomail/__main__.py 2>&1

# 3. Verify environment variables not used
grep -r "YOMAIL_" /home/user/yomail/src/

# 4. Count features
uv run python3 -c "
from yomail.pipeline.features import LineFeatures
from dataclasses import fields
print('Feature count:', len(fields(LineFeatures)))
"

# 5. Check model size
ls -la /home/user/yomail/src/yomail/data/email_body.crfsuite
```
