# Worker Template Tests

Unit tests for the TemplateWorker — the canonical reference implementation used as a starting point for new workers.

## Purpose

This directory contains tests that validate the TemplateWorker contract. The test file serves as both a validation suite and a copy-paste template when creating tests for new workers:
- Validates that TemplateWorker correctly implements the BaseWorker contract
- Demonstrates the standard test patterns for mocking and asserting worker behavior
- Provides a starting point for worker-specific test suites

## Directory Structure

```
tests/
├── __init__.py      - Python package marker
└── test_worker.py   - Tests for TemplateWorker (template for new worker test suites)
```

## How to Use

```bash
# Run from the workers root
cd artifacts/canonical/workers/TEMPLATE
pytest tests/ -v
```

When creating a new worker, copy `test_worker.py` and adapt it:
1. Replace `TemplateWorker` with your worker class name
2. Add worker-specific test cases
3. Add mocks for external dependencies (ML models, APIs, etc.)

## Content Index

| File | Description |
|---|---|
| `__init__.py` | Python package marker |
| `test_worker.py` | Template test suite for TemplateWorker (copy when creating new workers) |
