# 3D Mesh Prototyping Cell – Backend Scripts

## Purpose

Backend execution scripts for the **3D Mesh Prototyping Cell** — implements a single image-to-3D reconstruction pipeline with a hybrid job queueing architecture supporting multiple generation modes.

## Architecture

```
Manager Cell (Kind/Linux)     Windows Worker (GPU)
├─ API endpoint handling       ├─ InstantMesh processing
├─ Job queue management        └─ Blender post-processing
└─ Result retrieval
```

**Generation Modes**:
- `cloud-api` — External API-based generation (future integration)
- `local-gpu` — Redis-based job queueing for Windows Worker GPU
- `manual-upload` — Direct file upload without processing

## Content Index

| File | Description |
|------|-------------|
| [`__init__.py`](./__init__.py) | Package marker |
| [`main.py`](./main.py) | `MeshPrototypingCell` BaseCell + `execute_cell()` wrapper — Phase 6 hybrid generation mode routing |
| [`stable_fast_3d_client.py`](./stable_fast_3d_client.py) | HTTP client for Stable-Fast-3D API — job submission, status polling, result download |
| [`REFACTORING_SUMMARY.md`](./REFACTORING_SUMMARY.md) | Documentation of the Phase 6 refactoring changes |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`job_queue/`](./job_queue/) | Job queue management — Redis-based queue operations, job state machine |

## Related

- [`../`](../) — 3D Mesh Prototyping Cell backend root
- [`../../png-generator-cell/`](../../png-generator-cell/) — Often used upstream to generate input images
