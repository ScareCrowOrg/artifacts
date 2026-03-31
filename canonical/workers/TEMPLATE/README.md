# Worker Template

Canonical scaffold for creating new ScareVerseLab worker services.
Copy this directory to `artifacts/canonical/workers/<your-worker-name>/` and
implement the worker-specific logic in `worker.py`.

## Purpose

Provides a consistent starting point so every worker follows the same
file layout, dependency pattern, and test structure.  New workers inherit
the platform's health-check, job-polling, and error-handling boilerplate
without having to rewrite it.

## Content Index

| File / Directory | Description |
|-----------------|-------------|
| `__init__.py` | Package marker |
| `main.py` | Entry point — starts the worker event loop and wires dependencies |
| `worker.py` | **Primary implementation file** — override `process_job()` with worker logic |
| `requirements.txt` | Python dependencies for this worker |
| `tests/` | Unit tests for the worker |
| `tests/__init__.py` | Test package marker |
| `tests/test_worker.py` | Example test cases demonstrating the expected testing pattern |

## Usage

```bash
# Copy template
cp -r artifacts/canonical/workers/TEMPLATE artifacts/canonical/workers/my-worker

# Install dependencies
pip install -r artifacts/canonical/workers/my-worker/requirements.txt

# Run tests
pytest artifacts/canonical/workers/my-worker/tests/
```

## Related Documentation

- [Workers Directory](../README.md) — other canonical worker implementations
- [Canonical Artifacts](../../README.md) — parent canonical directory
