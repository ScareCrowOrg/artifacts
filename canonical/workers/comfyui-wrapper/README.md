# ComfyUI Wrapper Worker

Canonical implementation of the ComfyUI image-generation worker for
ScareVerseLab.  Wraps the ComfyUI inference service and exposes it as a
platform-compatible job-queue worker.

## Purpose

Enables AI image generation inside notebook cells using ComfyUI's SDXL
pipeline.  Creative workflows submit text-to-image jobs to this worker
and receive generated images as base64-encoded results.

## Content Index

| File / Directory | Description |
|-----------------|-------------|
| `main.py` | Entry point — configures and starts the ComfyUI worker loop |
| `worker.py` | Core job handler — translates job parameters to ComfyUI API calls and handles results |
| `requirements.txt` | Python dependencies (httpx) |

## Related Documentation

- [Stable Diffusion Wrapper](../stable-diffusion-wrapper/) — peer worker being replaced
- [Rembg Worker](../rembg/) — background-removal peer worker
- [Canonical Workers](../README.md) — all canonical worker implementations
