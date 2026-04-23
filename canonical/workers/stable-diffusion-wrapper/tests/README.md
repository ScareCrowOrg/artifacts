# Stable Diffusion Wrapper Worker Tests

Test directory for the Stable Diffusion Wrapper worker. Currently contains only the package marker.

## Purpose

This directory is the designated location for unit tests for the Stable Diffusion Wrapper worker. Tests should validate:
- BaseWorker contract compliance
- Image generation request formatting and response parsing
- Error handling for Stable Diffusion service unavailability
- Output format (base64-encoded images, metadata)

## Directory Structure

```
tests/
└── __init__.py   - Python package marker (tests to be added)
```

## How to Use

```bash
# Run from the stable-diffusion-wrapper worker root
cd artifacts/canonical/workers/stable-diffusion-wrapper
pytest tests/ -v
```

## Content Index

| File | Description |
|---|---|
| `__init__.py` | Python package marker |
