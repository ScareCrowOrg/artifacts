---
processed: true
processed_date: 2026-03-28
themes:
  - workers
  - stable-diffusion
  - ai
modules:
  - infrastructure
code_verified: true
dead_docs_found: false
---
# Stable Diffusion FastAPI Service

GPU-accelerated image generation service with FastAPI wrapper for GateKeeper integration.

## Overview

This service provides a FastAPI wrapper around Stable Diffusion (SD 1.5 and SDXL) for high-performance image generation. GateKeeper routes `sd_generate` jobs to this service via HTTP POST.

### Architecture

```
GateKeeper (job dispatcher)
    ↓ (POST /generate)
Stable Diffusion FastAPI Service (scareverse-sd-service)
    ↓ (lazy model loading)
NVIDIA GPU (CUDA inference)
    ↓ (base64 PNG response)
GateKeeper (result persistence)
```

## Endpoints

### POST /generate

Generate image from text prompt.

**Request:**
```json
{
  "model": "stabilityai/stable-diffusion-xl-base-1.0",
  "prompt": "a beautiful landscape with mountains",
  "negative_prompt": "blurry, low quality",
  "width": 512,
  "height": 512,
  "num_inference_steps": 20,
  "guidance_scale": 7.5,
  "seed": -1
}
```

**Response (success):**
```json
{
  "status": "success",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEA...",
  "model": "stabilityai/stable-diffusion-xl-base-1.0"
}
```

**Response (error):**
```json
{
  "status": "error",
  "error": "GPU out of memory"
}
```

### GET /health

Health check endpoint (does not validate GPU).

**Response:**
```json
{
  "status": "healthy"
}
```

## Building

Build the Docker image:

```bash
cd artifacts/canonical/services/stable-diffusion
docker-compose build
```

## Running

Start the service:

```bash
docker-compose up -d
```

View logs:

```bash
docker-compose logs -f stable-diffusion
```

Stop the service:

```bash
docker-compose down
```

## Testing

### Health Check

```bash
curl http://localhost:9090/health
```

### Generate Image

```bash
curl -X POST http://localhost:9090/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a beautiful landscape",
    "num_inference_steps": 10
  }'
```

## Configuration

### Environment Variables

- `HF_HUB_CACHE`: HuggingFace model cache directory (default: `/root/.cache/huggingface`)
- `HF_HUB_OFFLINE`: Set to `0` to download models from HuggingFace (default: `0`)

### Volume Mounts

- **HuggingFace cache**: Bind mount for persistent model storage
  - Default: `${HF_HUB_CACHE_PATH:-/root/.cache/huggingface}` → `/root/.cache/huggingface`
  - Required for model caching across container restarts

## Performance

Approximate generation times (RTX 4070, SDXL):

| Steps | Resolution | Time |
|-------|-----------|------|
| 10 | 512×512 | 8–15s |
| 20 | 512×512 | 15–25s |
| 50 | 768×768 | 60–90s |

First request loads model (~30-60s depending on model size).

## Troubleshooting

### CUDA Out of Memory

**Error**: `GPU out of memory`

**Solutions:**
- Reduce `num_inference_steps` (20 → 10)
- Reduce image size (512 → 256)
- Wait for other GPU jobs to complete
- Restart the container to clear CUDA cache

### Model Not Found

**Error**: `Model loading failed`

**Solutions:**
- Verify model ID on HuggingFace (e.g., `stabilityai/stable-diffusion-xl-base-1.0`)
- Check container logs: `docker logs scareverse-sd-service`
- Ensure HuggingFace cache volume is mounted
- Pre-download models to cache:
  ```bash
  docker exec scareverse-sd-service python -c \
    "from diffusers import AutoPipelineForText2Image; \
    AutoPipelineForText2Image.from_pretrained('stabilityai/stable-diffusion-xl-base-1.0')"
  ```

### Slow Generation

**Issue**: First request takes 30-60s

**Reason**: Model lazy-loading. Subsequent requests are faster.

**Solution**: Pre-warm the service with a dummy request after startup.

## Integration with GateKeeper

GateKeeper automatically routes `sd_generate` jobs to this service.

**Job Type Config** (`artifacts/canonical/job-types/sd_generate.json`):
```json
{
  "name": "sd_generate",
  "execution_model": "service",
  "service": {
    "endpoint": "http://scareverse-sd-service:9090"
  }
}
```

**Job Submission**:
```python
import redis
import json

r = redis.Redis(host="localhost", port=6380)
job = {
    "job_id": "gen-001",
    "type": "sd_generate",
    "payload": {
        "prompt": "a beautiful landscape",
        "num_inference_steps": 20
    }
}
r.lpush("scareverse:cpu-jobs:queue", json.dumps(job))

# Results stored in: scareverse:sd-results:gen-001
```

## Architecture Notes

### Lazy Model Loading

Models are loaded on first request and kept in GPU memory for subsequent requests. If a different model is requested, the previous model is unloaded.

### GPU Memory Management

- SDXL Base 1.0: ~8–10GB VRAM (FP16)
- SD 1.5: ~4–6GB VRAM (FP16)
- Keep-alive timeout: Models stay in memory for ~5 minutes of idle time

### Multi-Model Support

Supports any HuggingFace model compatible with `AutoPipelineForText2Image`:
- Stable Diffusion 1.5
- Stable Diffusion XL (SDXL)
- Custom fine-tuned models

## Files

- **Dockerfile**: Multi-stage build with PyTorch + diffusers
- **sd_api.py**: FastAPI application with `/generate` and `/health` endpoints
- **test_gpu.py**: GPU availability test script
- **docker-compose.yml**: Service configuration with GPU support

## References

- [Hugging Face Diffusers](https://huggingface.co/docs/diffusers)
- [Stable Diffusion Models](https://huggingface.co/stabilityai)
- [GateKeeper Job Types](../gatekeeper/config.py)
