---
processed: true
processed_date: 2025-12-09
themes:
  - testing
  - backend
  - frontend
  - quality-assurance
modules:
  - backend
  - frontend
  - testing
code_verified: true
dead_docs_found: false
---
# Linting Tests

This directory contains test files specifically designed to validate that our linting configuration (Pylint with pylint-pydantic plugin) correctly detects various code quality issues.

## Purpose

These tests serve as regression tests for linting capabilities. They contain **intentional errors** that should be detected by static analysis tools.

## Test Files

### `test_pydantic_field_validation.py`

**Purpose**: Verify that Pylint detects invalid field access on Pydantic models.

**Intentional Error**: Attempts to access `cell.fragmentos` (Portuguese) instead of the correct `cell.fragments` (English).

**Expected Behavior**: 
- When run with Python: Raises `ValueError: "Cell" object has no field "fragmentos"`
- When run with Pylint: Should ideally detect the field access error (W0201 or E1101)

**Current Status**: 
- ✅ Runtime detection: Pydantic correctly rejects invalid field access
- ⚠️  Static detection: Pylint with pylint-pydantic does not currently catch this specific pattern
  - This is a limitation of static analysis with dynamically generated Pydantic fields
  - The plugin helps with false positives but may not catch all field access errors

**Note**: While static detection would be ideal, the primary benefit of pylint-pydantic is:
1. **Eliminating false positives** on valid Pydantic code (previously ignored via `ignored-classes`)
2. **Enabling type checking** for Pydantic models
3. **Improving IDE integration** and autocomplete

The bug fix in `state_manager.py` (changing `fragmentos` to `fragments`) was necessary regardless of static detection capabilities.

## Running Tests

### Run Pylint on test files:
```bash
cd backend
python3 -m pylint tests/linting/test_pydantic_field_validation.py
```

### Run the test file to see runtime error:
```bash
cd backend
PYTHONPATH=/home/runner/_work/ScareVerseLab/ScareVerseLab/backend python3 tests/linting/test_pydantic_field_validation.py
```

Expected: `ValueError: "Cell" object has no field "fragmentos"`

## Integration with RULESET.md

These linting tests support:
- **Rule 4.3**: Technical naming convention (English names for technical identifiers)
- **Rule 3.1**: Test coverage and quality assurance

## Future Enhancements

Consider adding:
1. **Mypy integration** for stronger type checking on Pydantic models
2. **Ruff linter** as a faster alternative with native Pydantic support
3. **Pre-commit hooks** to catch errors before commit
4. Additional test cases for other common Pydantic validation scenarios

---

**Last Updated**: 2025-12-07  
**Maintained By**: Backend Agent
