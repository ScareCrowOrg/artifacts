# Rembg Worker

Canonical implementation of the background-removal worker for ScareVerseLab.
Uses the `rembg` library to strip backgrounds from images submitted via the
platform job queue.

## Purpose

Provides AI-powered background removal as a platform service.  Notebook cells
in creative workflows can submit image jobs to this worker and receive
background-free PNG results.

## Content Index

| File / Directory | Description |
|-----------------|-------------|
| `main.py` | Entry point — configures and starts the rembg worker loop |
| `worker.py` | Core job handler — loads images, runs rembg inference, returns result |
| `requirements.txt` | Python dependencies (rembg, Pillow, onnxruntime, etc.) |
| `tests/` | Unit/integration tests for the worker |
| `tests/__init__.py` | Test package marker |
| `tests/test_worker.py` | Test cases covering image input/output handling |

## Related Documentation

- [Worker Template](../TEMPLATE/) — base scaffold this worker is derived from
- [Stable Diffusion Worker](../stable-diffusion-wrapper/) — complementary image-generation worker
- [Canonical Workers](../README.md) — all canonical worker implementations
