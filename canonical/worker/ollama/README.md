# Ollama Queue Consumer Worker

Standalone Ollama LLM worker for ScareVerse. Extracts Ollama from `docker-compose.scarenode.yml` into an independent, reusable stack.

## Architecture

```
Backend Router (ollama_proxy.py)
  └─ RPUSH → scareverse:ollama-jobs:queue
               ↓ BRPOP
         ollama-consumer (this worker)
               ↓ POST /api/generate or /api/chat
         ollama service (ollama/ollama:latest)
               ↓ result
         ollama-consumer
               ↓ RPUSH → scareverse:ollama-results:{job_id}
         Backend Router
               ↓ BRPOP (300s timeout)
         Response to client
```

## Services

| Service | Image | Role |
|---|---|---|
| `ollama` | `ollama/ollama:latest` | GPU LLM inference on port 11434 (internal) |
| `ollama-consumer` | Built from `Dockerfile` | Redis queue consumer + Ollama API bridge |

## Job Schema

### Input (pushed by backend router to `scareverse:ollama-jobs:queue`)

**Generate job (`type: ollama_generate`):**
```json
{
  "job_id": "uuid-string",
  "type": "ollama_generate",
  "payload": {
    "prompt": "Tell me about ScareVerse",
    "model": "mistral",
    "stream": false,
    "options": {}
  },
  "created_at": 1234567890.123,
  "attempts": 0
}
```

**Chat job (`type: ollama_chat`):**
```json
{
  "job_id": "uuid-string",
  "type": "ollama_chat",
  "payload": {
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "mistral",
    "stream": false,
    "options": {}
  },
  "created_at": 1234567890.123,
  "attempts": 0
}
```

### Output (stored by worker at `scareverse:ollama-results:{job_id}`)

**Success:**
```json
{
  "status": "success",
  "data": {
    "response": "Generated text...",
    "model": "mistral"
  },
  "error": null
}
```

**Error:**
```json
{
  "status": "error",
  "data": null,
  "error": "Ollama request timed out"
}
```

## Setup

### Prerequisites

- Docker Desktop with GPU support
- NVIDIA Container Toolkit
- External Docker network: `docker network create scareverse-net`

### Windows Model Cache Binding

Ollama models are stored at `C:\Users\{USERNAME}\.ollama` on Windows. Configure via `.env`:

```env
# .env
OLLAMA_MODELS_PATH=C:\Users\YourUsername\.ollama
REDIS_L1_HOST=redis-local
REDIS_L1_PORT=6380
REDIS_L1_PASSWORD=scarerunner
LOG_LEVEL=INFO
```

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
docker-compose logs -f ollama-consumer
docker-compose logs -f ollama
```

## Health Check

```bash
curl http://localhost:8080/health
# {"status": "ok", "service": "ollama-consumer"}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_L1_HOST` | `redis-local` | Redis hostname |
| `REDIS_L1_PORT` | `6380` | Redis port |
| `REDIS_L1_PASSWORD` | `scarerunner` | Redis password |
| `REDIS_L1_DB` | `0` | Redis database |
| `JOB_QUEUE` | `scareverse:ollama-jobs:queue` | Input queue name |
| `RESULTS_KEY_PREFIX` | `scareverse:ollama-results` | Result key prefix |
| `BRPOP_TIMEOUT` | `300` | BRPOP timeout (seconds) |
| `RESULT_KEY_TTL` | `60` | Result auto-cleanup TTL |
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama service URL |
| `OLLAMA_REQUEST_TIMEOUT` | `120` | Inference timeout (seconds) |
| `OLLAMA_MODELS_PATH` | `/root/.ollama` | Windows model cache path |
| `LOG_LEVEL` | `INFO` | Log verbosity |

## GateKeeper Integration

When GateKeeper orchestration is needed (Phase 2), this worker can be extended to support L1/L2 multi-source pooling. The current single-queue implementation is fully compatible with the backend router.

## PNG Generator Cell Integration

The PNG generator cell uses the backend Ollama router (`POST /api/generate`) which transparently queues to this worker. No changes needed in the cell.

## VRAM Requirements

- `mistral` (7B): ~4GB VRAM
- `llama2` (7B): ~4GB VRAM
- `phi3` (3.8B): ~2.5GB VRAM

Monitor VRAM usage: `nvidia-smi`
