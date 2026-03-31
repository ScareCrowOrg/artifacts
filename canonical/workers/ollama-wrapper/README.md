# Ollama Wrapper Worker

Canonical implementation of the Ollama LLM inference worker for ScareVerseLab.
Wraps the locally-running Ollama server and exposes it as a platform-compatible
worker that polls for jobs, runs LLM inference, and returns structured responses.

## Purpose

Provides a reference implementation for integrating a self-hosted LLM (via Ollama)
into the ScareVerseLab job queue.  Used by notebook cells that require text
generation, summarisation, code assistance, or chat functionality.

## Content Index

| File / Directory | Description |
|-----------------|-------------|
| `main.py` | Entry point — configures and starts the Ollama worker loop |
| `worker.py` | Core job handler — sends prompts to the Ollama API and formats responses |
| `requirements.txt` | Python dependencies (httpx, ollama client, etc.) |
| `tests/` | Unit/integration tests for the worker |
| `tests/__init__.py` | Test package marker |

## Related Documentation

- [Worker Template](../TEMPLATE/) — base scaffold this worker is derived from
- [Stable Diffusion Worker](../stable-diffusion-wrapper/) — image-generation peer worker
- [Canonical Workers](../README.md) — all canonical worker implementations
