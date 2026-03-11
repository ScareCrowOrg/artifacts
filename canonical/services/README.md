---
processed: true
processed_date: 2026-03-09
themes:
  - services
  - architecture
  - docker
modules:
  - services
code_verified: true
dead_docs_found: false
---

# artifacts/canonical/services/

Infrastructure services for ScareVerse — long-lived Docker containers managed
separately from ephemeral subprocess job workers.

## Services

| Directory | Type | Purpose |
|-----------|------|---------|
| `backend/` | Docker (Python 3.11 + Node.js) | Backend API (FastAPI/uvicorn) + Gemini CLI |
| `vite/` | Docker (Node 20-alpine) | Vite dev server for on-demand TS/Vue compilation |
| `redis/` | Docker (redis:7-alpine) | Redis L1 local cache (port 6380) |
| `gatekeeper/` | Docker (FastAPI) | Unified job dispatcher (L1/L2 Redis → workers) |
| `ollama/` | Docker (Ollama image) | LLM inference service |
| `stable-diffusion/` | Docker (SD image) | Image generation service |

## Architecture

```
GateKeeper Service
    ↓ BRPOP L1/L2 Redis
    ↓ job {job_type, input_data}
    ├─ execution_model: "service"    → HTTP POST to service endpoint
    └─ execution_model: "subprocess" → spawn worker from artifacts/workers/
```

GateKeeper reads job-type definitions from `artifacts/canonical/job-types/*.json`
to determine the execution model and routing for each job type.

## Starting Services

```bash
# Full stack (meta-orchestrator - recommended)
docker-compose -f artifacts/canonical/services/docker-compose.yml up

# Individual services
docker-compose -f artifacts/canonical/services/redis/docker-compose.yml up -d
docker-compose -f artifacts/canonical/services/backend/docker-compose.yml up -d
docker-compose -f artifacts/canonical/services/vite/docker-compose.yml up -d

# GateKeeper
cd services/gatekeeper && docker-compose up -d

# Ollama (GPU required)
cd services/ollama && docker-compose up -d

# Stable Diffusion (GPU required)
cd services/stable-diffusion && docker-compose up -d
```

## Volume Mounts (GateKeeper)

GateKeeper mounts `artifacts/` so it can:
1. Discover and execute subprocess workers from `workers/`
2. Import shared utilities from `shared/`
3. Read job-type configs from `job-types/`

```yaml
volumes:
  - ../../../../:/app/artifacts:cached
environment:
  PYTHONPATH: /app/artifacts
  WORKERS_PATH: /app/artifacts/canonical/workers
```

## Key Changes from v1 (worker/ → services/)

- GateKeeper moved from `worker/gatekeeper/` → `services/gatekeeper/`
- Ollama moved from `worker/ollama/` → `services/ollama/` (docker-compose only)
- Stable Diffusion moved from `worker/stable-diffusion/` → `services/stable-diffusion/` (docker-compose only)
- Added `job_executor.py` for subprocess dispatch
- Added `service_executor.py` for HTTP dispatch (extracted from main.py)
- Updated `config.py` to support `execution_model` routing
