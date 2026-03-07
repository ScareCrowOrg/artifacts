# Stable Diffusion Queue Consumer Worker

Standalone Stable Diffusion worker for ScareVerse. Extracts ScareNode-SD from `docker-compose.scarenode.yml` into an independent, reusable stack.

## Architecture

```
Backend Router (stable_diffusion_queue.py)
  └─ RPUSH → scareverse:sd-jobs:queue
               ↓ BRPOP
         sd-consumer (this worker)
               ↓ POST /generate
         scarenode-sd service (diffusers + SDXL)
               ↓ image_base64 + model
         sd-consumer
               ↓ RPUSH → scareverse:sd-results:{job_id}
         Backend Router
               ↓ BRPOP (300s timeout)
         Response to client
```

## Services

| Service | Image | Role |
|---|---|---|
| `scarenode-sd` | Built from `infrastructure/stable-diffusion/` | GPU SDXL image generation on port 9090 (internal) |
| `sd-consumer` | Built from `Dockerfile` | Redis queue consumer + SD API bridge |

## VRAM Requirements

| Model | VRAM Required |
|---|---|
| `stabilityai/stable-diffusion-xl-base-1.0` (SDXL) | 8-10 GB |
| `runwayml/stable-diffusion-v1-5` (SD 1.5) | 4-6 GB |

⚠️ Minimum recommended GPU: RTX 3080 (10GB) or RTX 4070 (12GB)

## Job Schema

### Input (pushed by backend router to `scareverse:sd-jobs:queue`)

```json
{
  "job_id": "uuid-string",
  "type": "sd_generate",
  "payload": {
    "prompt": "A cute ghost holding a lantern, flat lighting, white background",
    "model": "stabilityai/stable-diffusion-xl-base-1.0",
    "negative_prompt": "blur, shadow, realistic",
    "height": 512,
    "width": 512,
    "num_inference_steps": 20,
    "guidance_scale": 7.5,
    "seed": -1
  },
  "created_at": 1234567890.123,
  "attempts": 0
}
```

### Output (stored by worker at `scareverse:sd-results:{job_id}`)

**Success:**
```json
{
  "status": "success",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCA...",
  "model": "stabilityai/stable-diffusion-xl-base-1.0",
  "processing_time_ms": 8500.0
}
```

**Error:**
```json
{
  "status": "error",
  "image_base64": null,
  "model": null,
  "error": "SD generation request timed out"
}
```

## Setup

### Prerequisites

- Docker Desktop with GPU support
- NVIDIA Container Toolkit (8-10GB VRAM for SDXL)
- External Docker network: `docker network create scareverse-net`

### Windows HuggingFace Cache Binding

SD models are downloaded from HuggingFace and cached locally. Configure via `.env`:

```env
# .env
HF_HUB_CACHE_PATH=C:\Users\YourUsername\.cache\huggingface
REDIS_L1_HOST=redis-local
REDIS_L1_PORT=6380
REDIS_L1_PASSWORD=scarerunner
LOG_LEVEL=INFO
# Optional: change model
SD_MODEL=stabilityai/stable-diffusion-xl-base-1.0
```

### First-time Model Download

On first startup, SDXL (~7GB) will be downloaded from HuggingFace. This can take 10-30 minutes depending on connection speed. Subsequent starts use the cached model.

### Start

```powershell
# From this directory:
docker-compose up -d
```

### Stop

```powershell
docker-compose down
```

### View Logs

```powershell
docker-compose logs -f sd-consumer
docker-compose logs -f scarenode-sd
```

## Health Checks

**SD Consumer:**
```bash
curl http://localhost:8081/health
# {"status": "ok", "service": "sd-consumer"}
```

**ScareNode-SD API:**
```bash
# From inside Docker network:
curl http://scarenode-sd:9090/health
# {"status": "healthy"}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_L1_HOST` | `redis-local` | Redis hostname |
| `REDIS_L1_PORT` | `6380` | Redis port |
| `REDIS_L1_PASSWORD` | `scarerunner` | Redis password |
| `REDIS_L1_DB` | `0` | Redis database |
| `JOB_QUEUE` | `scareverse:sd-jobs:queue` | Input queue name |
| `RESULTS_KEY_PREFIX` | `scareverse:sd-results` | Result key prefix |
| `BRPOP_TIMEOUT` | `300` | BRPOP timeout (seconds) |
| `RESULT_KEY_TTL` | `120` | Result auto-cleanup TTL |
| `SD_HOST` | `http://scarenode-sd:9090` | SD service URL |
| `SD_REQUEST_TIMEOUT` | `300` | Generation timeout (seconds) |
| `SD_MODEL` | `stabilityai/stable-diffusion-xl-base-1.0` | Default model |
| `HF_HUB_CACHE_PATH` | `/root/.cache/huggingface` | Windows model cache path |
| `LOG_LEVEL` | `INFO` | Log verbosity |

## GateKeeper Integration

When GateKeeper orchestration is needed (Phase 2), this worker can be extended to support L1/L2 multi-source pooling and VRAM-aware requeuing. The current single-queue implementation is fully compatible with the backend router.

## PNG Generator Cell Integration

The PNG generator cell uses the backend SD router (`POST /api/images/generate`) which transparently queues to this worker. No changes needed in the cell.

## VRAM Management

SDXL occupies ~8-10GB of VRAM during inference. When sharing GPU with Ollama or InstantMesh:
- Ensure total VRAM > 12GB, or coordinate sequential model loading
- Phase 2 will add VRAM orchestration via GateKeeper telemetry

Monitor VRAM usage: `nvidia-smi`
