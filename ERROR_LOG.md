# PARWA Error Log
This file tracks every error, its root cause, fix applied, and prevention note across all 60 weeks of development.

## Initialization
Error log created for Week 1 Day 2. No errors logged yet.

---

## Week 28 - 90% Accuracy Test Failures

**Date:** 2026-03-26
**Test File:** `tests/agent_lightning/test_90_accuracy.py`
**Tests Failed:** 2 of 26

### Error Description
Two tests in the 90% accuracy test suite were failing:
1. `TestAccuracyValidatorWeek28::test_full_validation` - Accuracy 87.4% < 88% threshold
2. `TestTrainingRunIntegration::test_full_training_and_validation` - Similar accuracy issue

### Root Cause
The tests used Python's `hash()` function with string arguments to generate test predictions:
```python
"correct": hash(str(_)) % 10 < 9  # Intended 90% accuracy
```

Since Python 3.3, hash randomization is enabled by default for strings (`PYTHONHASHSEED`). This causes `hash(str(_))` to produce different values across Python sessions, resulting in non-deterministic test data distribution. Instead of the expected 90% correct predictions, the actual distribution varied (e.g., 87.4%).

### Fix Applied
Replaced hash-based generation with deterministic index-based logic:
```python
# Before (non-deterministic)
"correct": hash(str(_)) % 10 < 9

# After (deterministic - exactly 900 correct, 100 incorrect)
"correct": i < 900
```

This ensures exactly 90% accuracy in test predictions (900 correct out of 1000 total).

### Prevention Notes
1. **Avoid `hash()` for test data generation** - Use deterministic approaches instead
2. **Use explicit distributions** - For percentage-based tests, create exact counts (e.g., 900 correct + 100 incorrect)
3. **Use `random.seed()`** if randomness is needed - Makes tests reproducible
4. **Test assertions should match generated data** - If generating 90% correct, assert >= 90% not >= 88%

### Verification
After fix: All 26 tests in `test_90_accuracy.py` pass (100%)

---

## Week 28 - Privacy Validation Test Failure

**Date:** 2026-03-26
**Test File:** `tests/agent_lightning/test_v2.py`
**Tests Failed:** 2 (`test_privacy_validation`, `test_client_anonymization`)

### Error Description
The privacy validation test was failing because the anonymized client IDs were being flagged as non-anonymized.

### Root Cause
In `collective_dataset_builder.py`:
- `_anonymize_client_id()` created IDs like `client_{hash}` (e.g., `client_a1b2c3d4`)
- `validate_privacy()` checked if IDs start with `client_` to detect non-anonymized IDs
- This caused ALL anonymized IDs to fail the privacy check!

The logic was contradictory - anonymized IDs still started with `client_`, triggering the "non-anonymized" detection.

### Fix Applied
Changed the anonymized ID prefix from `client_` to `anon_`:

```python
# Before (contradictory - anonymized IDs still started with "client_")
return f"client_{hash_val}"

# After (clear distinction - "anon_" prefix for anonymized IDs)
return f"anon_{hash_val}"
```

Also updated the test `test_client_anonymization` to expect `anon_` prefix.

### Prevention Notes
1. **Ensure anonymization is distinguishable** - Anonymized IDs should have a different format than original IDs
2. **Test edge cases** - Validate that privacy checks work correctly with the anonymization logic
3. **Use descriptive prefixes** - `anon_` clearly indicates an anonymized ID vs `client_` for real IDs

### Verification
After fix: All 313 tests in `tests/agent_lightning/` pass (100%)
