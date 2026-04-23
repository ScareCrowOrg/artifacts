# Ollama Wrapper Worker Tests

Test directory for the Ollama Wrapper worker. Currently contains only the package marker.

## Purpose

This directory is the designated location for unit tests for the Ollama Wrapper worker. Tests should validate:
- BaseWorker contract compliance
- LLM request/response formatting (Ollama API → worker output format)
- Error handling for Ollama service unavailability

## Directory Structure

```
tests/
└── __init__.py   - Python package marker (tests to be added)
```

## How to Use

```bash
# Run from the ollama-wrapper worker root
cd artifacts/canonical/workers/ollama-wrapper
pytest tests/ -v
```

## Content Index

| File | Description |
|---|---|
| `__init__.py` | Python package marker |
