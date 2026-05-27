# ComfyUI Service — Unified GPU Generation Runtime

## Overview

Single container running ComfyUI as the unified AI generation runtime for ScareVerse. Supports 2D image generation (SDXL, Flux) and 3D mesh generation (Hunyuan3D v2) via custom nodes.

## Architecture

```
┌───────────────────────────────────────────────────┐
│              ComfyUI Container                     │
│  ┌──────────────────────┐  ┌───────────────────┐  │
│  │   ComfyUI Engine     │  │ ScareVerse Wrapper │  │
│  │   Port 8188          │  │ Port 9090          │  │
│  │   - SDXL             │  │ - /health          │  │
│  │   - Flux              │  │ - /generate (TODO) │  │
│  │   - Hunyuan3D v2 FP8 │  │ - /workflow (TODO) │  │
│  └──────────────────────┘  └───────────────────┘  │
└───────────────────────────────────────────────────┘
```

## Endpoints

| Endpoint | Method | Status | Description |
|----------|--------|--------|-------------|
| `/health` | GET | ✅ Active | Returns `{"status": "healthy", "service": "comfyui"}` |
| `/generate` | POST | 🚧 Future | Image/mesh generation from prompt |
| `/workflow` | POST | 🚧 Future | Raw ComfyUI workflow execution |

## Setup

### Prerequisites

- Docker with NVIDIA Container Toolkit
- NVIDIA GPU with CUDA 12.1+ (tested on RTX 4070 12GB)
- ScareVerse Launcher installed

### Build

```bash
docker-compose -f artifacts/canonical/services/comfyui/docker-compose.yml build
```

### Run

```bash
docker-compose -f artifacts/canonical/services/comfyui/docker-compose.yml up -d
```

### Verify

```bash
# Health check
curl http://localhost:9090/health

# GPU detection
docker exec scareverse-comfyui-service python -c "import torch; print(torch.cuda.is_available())"

# Redis heartbeat
docker exec scareverse-redis-service redis-cli -a scarerunner -p 6380 EXISTS state:service:comfyui:available
```

## Custom Nodes Installed

| Node | Source | Purpose |
|------|--------|---------|
| ComfyUI-Manager | ltdrdata | Model/ workflow management UI |
| ComfyUI-Hunyuan3DWrapper | Kijai | Hunyuan3D v2 FP8 mesh generation |

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_L1_HOST` | `redis` | Redis L1 hostname |
| `REDIS_L1_PORT` | `6380` | Redis L1 port |
| `REDIS_L1_PASSWORD` | `scarerunner` | Redis password |
| `HEARTBEAT_INTERVAL` | `60` | Heartbeat interval (seconds) |
| `HEARTBEAT_TTL` | `180` | Redis key TTL (seconds) |
| `COMFYUI_PORT` | `8188` | ComfyUI internal port |
| `WRAPPER_PORT` | `9090` | Wrapper API port |

## Volumes

| Volume | Mount Point | Purpose |
|--------|-------------|---------|
| `comfyui-models` | `/app/comfyui/models` | Persistent model storage |
| `comfyui-output` | `/app/comfyui/output` | Generated outputs |
| Local log dir | `/app/logs` | Service logs |

## Troubleshooting

### Container crashes immediately
- Check GPU is accessible: `docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi`

### ComfyUI not accessible on 8188
- Port 8188 is optional (debug only). The wrapper on 9090 is the primary API.
- ComfyUI takes 2-5 minutes to start on first run (model loading).

### Out of memory
- Reduce batch size or use FP8 models
- RTX 4070 12GB handles Hunyuan3D v2 FP8 and SDXL without OOM

## Future

- Job type integration (comfyui_generate, hunyuan3d_generate)
- POST /generate and POST /workflow endpoint implementation
- GateKeeper integration
- Deprecation of stable-diffusion and instantmesh services
