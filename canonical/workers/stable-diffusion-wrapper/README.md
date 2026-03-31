# Stable Diffusion Wrapper Worker

Canonical implementation of the Stable Diffusion image-generation worker for
ScareVerseLab.  Wraps a locally-running Stable Diffusion service (e.g. AUTOMATIC1111
or ComfyUI) and exposes it as a platform-compatible job-queue worker.

## Purpose

Enables AI image generation inside notebook cells.  Creative workflows submit
text-to-image or image-to-image jobs to this worker and receive generated images
stored in the platform's object store.

## Content Index

| File / Directory | Description |
|-----------------|-------------|
| `main.py` | Entry point — configures and starts the Stable Diffusion worker loop |
| `worker.py` | Core job handler — translates job parameters to SD API calls and handles results |
| `requirements.txt` | Python dependencies (httpx, pillow, etc.) |
| `tests/` | Unit/integration tests for the worker |
| `tests/__init__.py` | Test package marker |

## Related Documentation

- [Worker Template](../TEMPLATE/) — base scaffold this worker is derived from
- [Rembg Worker](../rembg/) — background-removal peer worker
- [Ollama Wrapper](../ollama-wrapper/) — LLM inference peer worker
- [Canonical Workers](../README.md) — all canonical worker implementations
