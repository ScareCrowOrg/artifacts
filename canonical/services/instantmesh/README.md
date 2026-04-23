# InstantMesh Service

Canonical artifact for the InstantMesh 3D mesh generation service — a FastAPI service providing Redis-integrated 3D mesh generation from input images.

## Purpose

This directory contains the canonical definition for the InstantMesh service:
- **3D mesh generation**: Generates 3D meshes from input images using the InstantMesh model
- **Redis heartbeat**: Registers service availability in Redis L1 for GateKeeper discovery (without HTTP probing)
- **FastAPI API**: Exposes HTTP endpoints for mesh generation and health checking

## Directory Structure

```
instantmesh/
└── main.py   - FastAPI application entry point with /generate and /health endpoints
```

## How to Use

```bash
# Run the service directly
python main.py

# API endpoints
POST /generate   - Generate 3D mesh from base64-encoded input image
GET  /health     - Liveness and readiness check
```

### Request Format

```json
POST /generate
{
  "image": "<base64-encoded-image>",
  "output_format": "obj"
}
```

### Service Discovery

The service registers itself in Redis L1 at startup:
```
state:service:instantmesh:available → JSON heartbeat (TTL refreshed periodically)
```

## Content Index

| File | Description |
|---|---|
| `main.py` | FastAPI application: /generate endpoint, /health check, Redis L1 heartbeat registration |
