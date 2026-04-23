# Rembg Worker Tests

Unit tests for the RembgWorker — validates background removal processing without requiring rembg or ONNX to be installed.

## Purpose

This directory validates the RembgWorker's behavior under test conditions:
- Tests that RembgWorker correctly implements the BaseWorker contract
- Validates JSON I/O behavior (base64 image input/output format)
- Uses mocks to avoid requiring rembg/ONNX runtime dependencies during CI

## Directory Structure

```
tests/
├── __init__.py      - Python package marker
└── test_worker.py   - Tests for RembgWorker (background removal processing)
```

## How to Use

```bash
# Run from the rembg worker root
cd artifacts/canonical/workers/rembg
pytest tests/ -v

# No rembg/ONNX installation required — ML library is mocked
```

## Content Index

| File | Description |
|---|---|
| `__init__.py` | Python package marker |
| `test_worker.py` | Tests for RembgWorker with mocked rembg/ONNX dependencies |
