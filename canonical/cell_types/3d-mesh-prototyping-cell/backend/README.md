# 3D Mesh Prototyping Cell — Backend

Python backend for the 3D Mesh Prototyping Cell, implementing the Single Image-to-3D reconstruction pipeline with hybrid job queueing architecture.

## Purpose

This package provides the server-side execution logic for generating 3D mesh models from input images. It supports three generation modes (cloud-api, local-gpu, manual-upload) and uses a Redis-based job queue to offload GPU-intensive work to Windows Worker nodes.

## Index

### Files

| File | Description |
|------|-------------|
| `__init__.py` | Python package marker |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `scripts/` | Main execution script: `main.py` (cell execution logic), `stable_fast_3d_client.py` (client for the 3D generation service), `job_queue/` (Redis queue manager), `REFACTORING_SUMMARY.md` |
| `tests/` | Unit tests for the backend scripts |

## Architecture

```
execute-ephemeral endpoint
         ↓
  MeshPrototypingCell.execute() / execute_cell()
         ↓
  Generation Mode Routing
  ┌──────┬───────┬────────────┐
  │      │       │            │
cloud-api local-gpu manual-upload
  │      │       │
  │   Redis Job  │ Direct upload
  │   Queue      │
  │      ↓       │
  │  Windows Worker (InstantMesh + Blender)
  │      ↓       │
  └──────┴───────┴────────────┘
         ↓
  Standardized result (model URL, metadata)
```

### Generation Modes

| Mode | Description |
|------|-------------|
| `cloud-api` | External API-based generation (future integration placeholder) |
| `local-gpu` | Redis job queue → Windows Worker GPU processing (InstantMesh + Blender) |
| `manual-upload` | Direct file upload without processing |

## Key Classes

### `MeshPrototypingCell` (in `scripts/main.py`)

Implements `BaseCell` v1.0:
- `execute()` — routes to the appropriate generation mode
- `validate()` — checks input image and mode parameters
- `health_check()` — verifies Redis and worker connectivity
- `describe()` — returns cell metadata

## Usage

Invoked automatically by the platform `execute-ephemeral` endpoint. To run tests:

```bash
pytest artifacts/canonical/cell_types/3d-mesh-prototyping-cell/backend/tests/ -v
```

## Related Documentation

- [3D Mesh Prototyping Cell Root](../) - Full cell overview
- [3D Mesh Prototyping Frontend](../frontend/) - Vue frontend
- [Shared Types](../../../../shared/types/) - `BaseCell` interface
