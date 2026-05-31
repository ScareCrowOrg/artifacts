# ComfyUI Hunyuan3D Worker

Canonical implementation of the Hunyuan3D mesh-generation worker for
ScareVerseLab.  Wraps the ComfyUI Hunyuan3DWrapper inference service and
exposes it as a platform-compatible job-queue worker.

## Purpose

Enables 3D mesh generation inside notebook cells using ComfyUI's
Hunyuan3DWrapper pipeline.  Creative workflows submit image-to-3D jobs
to this worker and receive GLB meshes as base64-encoded results.

## Content Index

| File / Directory | Description |
|-----------------|-------------|
| `main.py` | Entry point — configures and starts the Hunyuan3D worker loop |
| `worker.py` | Core job handler — translates job parameters to ComfyUI API calls and handles results |
| `requirements.txt` | Python dependencies (httpx) |

## Related Documentation

- [ComfyUI Hunyuan3D Wrapper Service](../../services/comfyui/) — backing inference service
- [ComfyUI Wrapper Worker](../comfyui-wrapper/) — peer worker for 2D image generation
- [Canonical Workers](../README.md) — all canonical worker implementations
