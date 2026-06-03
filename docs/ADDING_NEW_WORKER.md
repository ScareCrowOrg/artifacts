---
processed: true
processed_date: 2026-03-06
themes:
  - official
  - architecture
  - atomic-workers
modules:
  - workers
code_verified: true
dead_docs_found: false
---

# Adding New Workers Guide

## Definition

**A Worker is a subprocess-based job processor in the BaseWorker pattern.**

Workers execute discrete operations orchestrated by **GateKeeper** via job dispatch. They may process locally (isolated venv) or call long-running services (Ollama, Stable Diffusion) over HTTP.

Workers are deployed via **Launcher** and are the **recommended execution model** for all job-type operations.

---

## Architecture Overview: ScareVerse Full Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    Viewers (UI Layer)                           │
│              Render cells & books dynamically                   │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Cell-Types & Book-Types │
                    │  (Composable Components)│
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Job-Types           │
                    │ (Orchestration Intent)  │
                    └────────────┬────────────┘
                                 │
                ┌────────────────▼────────────────────┐
                │          Workers                     │
                │  (BaseWorker Pattern - Subprocess)  │
                │                                     │
                ├─ OllamaWorker (calls /api/generate)│
                ├─ SDWorker (calls /api/generate)    │
                ├─ RembgWorker (local processing)    │
                └─ InstantMeshWorker (calls /process)│
                                 │
                ├────────────────┴────────────────────┤
                │                                     │
                ▼                                     ▼
         ┌─────────────┐                   ┌──────────────────┐
         │Local Process│                   │  Services (HTTP) │
         │  (Isolated  │                   │                  │
         │   venv)     │                   │  Ollama          │
         │             │                   │  Stable Diffusion│
         │ Rembg       │                   │  InstantMesh     │
         └─────────────┘                   └──────────────────┘
```

**Key Insight**: All job execution flows through **Workers (BaseWorker subclasses)**. Workers decide internally whether they need to call external services or process locally.

---

## Overview

### What is a Worker?

**A Worker is a BaseWorker subclass that processes discrete operations.**

Workers are **ephemeral** (spawn → execute → exit) and **isolated** (each job gets its own venv). They:
- Read job parameters from stdin (JSON)
- Process synchronously (call services or compute locally)
- Return results via stdout (JSON)

**Examples**: 
- Local: Image processing (Rembg - background removal)
- Service-calling: LLM inference (OllamaWorker calls Ollama service), Image generation (SDWorker calls SD service)

**All job workers should be subprocess-based** (execution_model: "subprocess"). This provides:
- ✅ venv isolation (each job gets fresh Python environment)
- ✅ Flexible processing (local or service-based)
- ✅ Resource cleanup (subprocess exits = all resources freed)
- ✅ Generic orchestration (GateKeeper doesn't care about implementation details)

### When to Create a Worker

Create a worker (subprocess-based) when you need to:
- ✅ **Add a new job type** that GateKeeper should orchestrate
- ✅ **Process locally** (isolated venv, no long-lived service needed)
- ✅ **Call a long-running service** (wrap HTTP calls to Ollama, SD, InstantMesh)
- ✅ **Support batch operations** (image processing, text generation, 3D mesh)
- ✅ **Manage heavy dependencies** (ML models, large libraries in isolated venv)

**When to use Workers that call Services:**
- ✅ OllamaWorker → calls `http://scareverse-ollama-service:11434/api/generate`
- ✅ StableDiffusionWorker → calls `http://scareverse-sd-service:9090/api/generate`
- ✅ InstantMeshWorker → calls `http://scareverse-worker-instantmesh:8000/process`
- ✅ RembgWorker → local processing (no service call)

**Don't create a worker when:**
- ❌ You need a **long-lived infrastructure service** (Traefik, Redis, MongoDB → use ADDING_NEW_SERVICE.md)
- ❌ You just need **UI logic** (implement as Cell-Type)
- ❌ You're **composing existing operations** (use Book-Types instead)
- ❌ The operation is **synchronous UI-only** (implement as Cell, not Worker)

---

## 🚨 MANDATORY REQUIREMENTS CHECKLIST

**For Subprocess Workers (BaseWorker Pattern):**

### Core Requirements
- [ ] **Self-contained folder** - `artifacts/canonical/workers/{name}/`
- [ ] **worker.py** - `BaseWorker` subclass implementing `execute()`
- [ ] **main.py** - CLI entry point (reads stdin JSON, writes stdout JSON)
- [ ] **requirements.txt** - All Python dependencies (no FastAPI/uvicorn for local processing)
- [ ] **Job-type JSON** - `artifacts/canonical/job-types/{name}.json` with:
  - `execution_model: "subprocess"`
  - `queue_type: "cpu"` or `"gpu"` (critical for GateKeeper orchestrator decisions)
  - `worker: {"path": "artifacts/canonical/workers/{name}", "entry_point": "main.py"}`
- [ ] **Tests** - Unit + integration tests, >80% coverage
- [ ] **README.md** - Setup, usage, configuration examples

### If Calling External Service (Ollama, SD, InstantMesh)
- [ ] Worker makes HTTP calls to service internally (worker decides, not GateKeeper)
- [ ] Job-type has `queue_type` matching service requirement (gpu for SD/InstantMesh, cpu for Ollama)
- [ ] Worker handles service unavailability gracefully (retries, timeouts)
- [ ] Example: OllamaWorker → `await httpx.post(f"{OLLAMA_HOST}/api/generate", json=payload)`

> **Template:** `cp -r artifacts/canonical/workers/TEMPLATE artifacts/canonical/workers/my-worker`
> **Examples:** `rembg/` (local), `ollama-wrapper/` (calls service), `stable-diffusion-wrapper/` (calls service)

---

## ⚠️ For Long-Lived Services?

**Are you building a long-lived infrastructure service instead?**
- Traefik, Cloudflared, Redis, Backend, Auth-Proxy, etc.
- **→ Use ADDING_NEW_SERVICE.md instead**

This guide is **ONLY for subprocess workers** (ephemeral job processors).

---

## Core Implementation (Required for All Workers)

All workers must follow these patterns to be deployable via Launcher and manageable as ScareVerse artifacts.

### Step 1: Create Worker Directory

> **For subprocess workers (recommended):**
> ```bash
> cp -r artifacts/canonical/workers/TEMPLATE artifacts/canonical/workers/my-worker
> cd artifacts/canonical/workers/my-worker
> ```
>
> **For service workers (long-lived Docker containers):**

```bash
mkdir -p artifacts/canonical/services/my-worker
cd artifacts/canonical/services/my-worker
mkdir -p tests
```

### Step 2: Create Dockerfile

**For subprocess workers:**
- ✅ `python:3.11-slim` base image
- ✅ Minimal system dependencies (only what's needed)
- ✅ Copy requirements.txt and pip install
- ✅ Copy worker source code (worker.py, main.py)
- ✅ **NO** EXPOSE (subprocess workers don't listen on ports)
- ✅ **NO** HTTP server (use stdin/stdout for I/O)

**Important**: Job workers expose internal ports on Docker network:
- **Ollama, Stable Diffusion style**: Port **8080** (recommended for CPU-heavy inference)
- **Rembg style**: Port **9000** (lightweight, alternative pattern)
- **Storage/Proxy workers**: Port **9001+** (if needing external access)
- Port is configured via `WORKER_PORT` env var in docker-compose.yml and config.py

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies (keep minimal - only curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

# EXPOSE will use WORKER_PORT from config (8000 default, 8080 for inference, 9000 for lightweight)
EXPOSE 8000

CMD ["python", "main.py"]
```

**Dockerfile Best Practices from Real Workers:**
- ✅ Keep image minimal (only curl for health, no unnecessary tools)
- ✅ Use `--no-cache-dir` for pip to reduce layer size
- ✅ Multi-stage build if worker has heavy build dependencies (ML models, etc)
- ✅ Copy requirements.txt first (cache layer optimization)
- ✅ Copy source files last (maximize cache hits)

### Step 3: Create docker-compose.yml

**Requirements:**
- ✅ External network: `scareverse-net` (required for GateKeeper routing)
- ✅ All config via environment variables
- ✅ Health check endpoint on internal port
- ✅ Restart policy: `unless-stopped` (ensures recovery)
- ✅ **No `ports:` for job workers** (communicate via Docker network internal only)
- ✅ Service/container naming: `scareverse-{worker-type}-worker` (critical for GateKeeper routing)

```yaml
version: "3.9"

services:
  my-worker:
    build: .
    image: scareverse-worker-my-worker:latest
    # IMPORTANT: Container name format: scareverse-{worker-type}-worker
    # GateKeeper routes to: http://scareverse-my-worker-worker:${WORKER_PORT}
    container_name: scareverse-my-worker-worker
    restart: unless-stopped

    # Job workers: NO external ports (communicate via Docker network only)
    # GateKeeper reaches at: http://scareverse-my-worker-worker:8000 (or 8080, 9000, etc)
    # Storage/Proxy workers: add ports section below if needing external access

    environment:
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      WORKER_ID: ${WORKER_ID:-my-worker-1}
      WORKER_PORT: ${WORKER_PORT:-8000}  # Port: 8000 (default), 8080 (inference), or 9000 (lightweight)

      # If GateKeeper integration (job worker):
      # REDIS_L1_HOST: ${REDIS_L1_HOST:-redis-local}
      # REDIS_L1_PORT: ${REDIS_L1_PORT:-6380}
      # REDIS_L1_PASSWORD: ${REDIS_L1_PASSWORD:-scarerunner}
      # REDIS_L1_DB: ${REDIS_L1_DB:-0}

    networks:
      - scareverse-net

    # Health check must use internal port (same as WORKER_PORT)
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${WORKER_PORT:-8000}/health"]
      interval: 30s
      timeout: 10s
      retries: 3

    # Graceful shutdown: allow time for SIGTERM cleanup
    stop_grace_period: 30s

networks:
  scareverse-net:
    external: true
```

**For Storage/Proxy Workers (if external access needed):**
```yaml
    # Add ports section ONLY if you need host access
    ports:
      - "${PORT:-9001}:${WORKER_PORT:-8000}"
    # Example: Minio on 9001, worker receives requests via Docker and host port 9001
```

**Naming Convention (Critical for GateKeeper Routing):**
- Service name in docker-compose: `my-worker` (arbitrary)
- Container name: `scareverse-{worker-type}-worker` (fixed pattern)
- GateKeeper discovers and routes to: `http://scareverse-{worker-type}-worker:${WORKER_PORT}`
- Must match `endpoint` field in job-type JSON exactly

### Step 4: Create requirements.txt

```
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
pydantic>=2.0.0
pyyaml>=6.0
redis>=4.0.0
httpx
```

**🚨 CRITICAL Dependencies for Service Workers:**

If your service uses `BaseService` for Redis L1 heartbeat (MANDATORY), you **MUST** include:
- `redis>=4.0.0` – Redis L1 connection for heartbeat registration
- `httpx` – Required by `canonical.shared.services.base_service` for HTTP operations

**Common Error** (if missing `httpx`):
```
ModuleNotFoundError: No module named 'httpx'
BaseService unavailable – initial heartbeat disabled
```

**Rule**: Any service that imports from `canonical.shared` needs both `redis` and `httpx`. Copy this as your minimum:
```
redis>=4.0.0
httpx
```

### Step 5: Create config.py

**Requirements:**
- ✅ All config from environment variables
- ✅ Sensible defaults (no hardcoding)
- ✅ No hardcoded IPs/ports
- ✅ Configurable WORKER_PORT (8000-9000 range)

```python
"""
Configuration for My Worker
"""

import os

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ============================================================================
# Worker Configuration
# ============================================================================

WORKER_ID = os.getenv("WORKER_ID", "my-worker-1")
# Job workers: port 8000 (inference), 8080 (common), or 9000 (lightweight)
# Set via WORKER_PORT env var in docker-compose.yml
WORKER_PORT = int(os.getenv("WORKER_PORT", "8000"))

# If this is a GateKeeper-integrated job worker, add these:
# SUPPORTED_JOB_TYPES = ["my_operation_v1", "my_operation_v2"]
# HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))  # seconds
# HEARTBEAT_TTL = HEARTBEAT_INTERVAL * 3  # TTL = 3x interval (60s typical)
# REDIS_L1_HOST = os.getenv("REDIS_L1_HOST", "redis-local")
# REDIS_L1_PORT = int(os.getenv("REDIS_L1_PORT", "6380"))
# REDIS_L1_PASSWORD = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
# REDIS_L1_DB = int(os.getenv("REDIS_L1_DB", "0"))
```

**Port Conventions (from real implementations):**
| Worker Type | Port | Example | Use Case |
|------------|------|---------|----------|
| **CPU-heavy inference** | 8080 | Ollama, Stable Diffusion | LLM, image generation |
| **Lightweight processing** | 9000 | Rembg | Background removal |
| **Generic job worker** | 8000 | Default if unsure | Any CPU task |
| **Storage/Proxy** | 9001+ | S3, Minio, Nginx | External access needed |

**If NOT doing GateKeeper integration** (just standalone worker):
- Only need: `LOG_LEVEL`, `WORKER_ID`, `WORKER_PORT`
- Skip: `SUPPORTED_JOB_TYPES`, `HEARTBEAT_*`, `REDIS_L1_*`

### Step 6: Create main.py or entrypoint.sh

**⚠️ IMPORTANT: FastAPI is OPTIONAL**

- **If you're building a job processor** (Ollama, Stable Diffusion style): Use FastAPI + uvicorn
- **If you're wrapping a native tool** (Traefik, Redis, Node service): Use language-native entry point or shell script

**For FastAPI-based services:**

**Requirements:**
- ✅ FastAPI app for HTTP interface
- ✅ Proper startup/shutdown lifecycle
- ✅ Graceful error handling
- ✅ Comprehensive logging

```python
"""
My Worker - Atomic operation microservice
"""

import logging
import sys
from fastapi import FastAPI
from pydantic import BaseModel

import config

# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="My Worker",
    description="Atomic worker for my operation",
    version="1.0.0",
)

# ============================================================================
# Models
# ============================================================================

class HealthResponse(BaseModel):
    status: str
    worker_id: str

# ============================================================================
# Lifecycle
# ============================================================================

@app.on_event("startup")
async def startup():
    logger.info(f"🚀 Starting {config.WORKER_ID}...")

    # 🚨 MANDATORY: Register service availability in Redis L1
    # All service workers MUST signal availability to GateKeeper via Redis L1 heartbeat
    # See: "Service Heartbeat Registration" section below
    from canonical.shared.services.base_service import BaseService
    import asyncio

    service = BaseService(config.WORKER_ID, logger=logger)
    asyncio.create_task(service.heartbeat())
    logger.info(f"✅ {config.WORKER_ID} started with heartbeat registration (state:service:{config.WORKER_ID}:available)")

@app.on_event("shutdown")
async def shutdown():
    logger.info("🛑 Shutting down...")
    logger.info("✅ Shutdown complete")

# ============================================================================
# HTTP Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe for Launcher health checks.

    Called on internal port 9000 via Docker network.
    GateKeeper monitors this endpoint to verify worker is alive.
    """
    return HealthResponse(
        status="healthy",
        worker_id=config.WORKER_ID,
    )

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.WORKER_PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
```

---

### Step 6b: Non-FastAPI Services (Native Tools)

**If you're NOT using FastAPI** (e.g., wrapping Traefik, Redis, Node app):

Create an **entrypoint.sh** script that:
1. Starts the native tool (e.g., `traefik`, `redis-server`, `npm start`)
2. Starts Python heartbeat in background (fire-and-forget or blocking)
3. Handles graceful shutdown (SIGTERM)

**Example (Traefik-style)**:
```bash
#!/bin/sh
# Start the native tool
traefik --configfile=/app/traefik.yml &
TOOL_PID=$!

# Start heartbeat daemon (fire-and-forget)
python3 /app/heartbeat.py || true
HEARTBEAT_PID=$!

# Graceful shutdown
_shutdown() {
    kill $HEARTBEAT_PID 2>/dev/null || true
    kill $TOOL_PID 2>/dev/null || true
    exit 0
}
trap _shutdown SIGTERM SIGINT SIGHUP

# Keep container alive
wait $TOOL_PID
```

**Example (Cloudflared-style, blocking heartbeat)**:
```bash
#!/bin/sh
# Start native tool in background
cloudflared tunnel run --token $TUNNEL_TOKEN &
TOOL_PID=$!

# Start heartbeat in foreground (blocking, part of PID 1)
python3 /app/heartbeat.py

# If heartbeat exits, stop container
exit $?
```

---

### 🚨 SERVICE HEARTBEAT REGISTRATION (MANDATORY for All Service Workers)

**CRITICAL REQUIREMENT**: Every service worker MUST register availability in Redis L1 on startup. This is how GateKeeper and other systems know your service is alive.

**Key Concepts:**

1. **What is a Heartbeat?**
   - A periodic signal that your service is alive and ready to handle requests
   - Stored in Redis L1 under key: `state:service:{service-name}:available`
   - TTL-based: automatically expires if service dies or crashes
   - Used by: GateKeeper, CentralHub, other orchestrators

2. **Heartbeat Implementation Patterns** (Choose one based on your service type)

   **Option A: Fire-and-Forget** (FastAPI + uvicorn services)
   - Heartbeat runs in background via `asyncio.create_task()`
   - Does NOT block service startup
   - Service starts immediately and accepts requests
   - Heartbeat refreshes independently every HEARTBEAT_INTERVAL seconds
   - Example: Backend, Ollama
   
   **Option B: Blocking Foreground** (Non-HTTP services like Cloudflared)
   - Heartbeat runs as main foreground task (part of PID 1)
   - Keeps container alive while heartbeat runs
   - Used when native tool doesn't need HTTP server
   - Example: Cloudflared waits in main loop with heartbeat

3. **BaseService Class** (Provided by Framework)
   - Location: `canonical/shared/services/base_service.py`
   - Handles all Redis L1 heartbeat logic
   - Method: `await service.heartbeat()` - refreshes key + TTL in background loop
   - Automatically handles TTL = 3 × HEARTBEAT_INTERVAL

**Implementation (Already in Step 6 above):**

```python
import asyncio
from canonical.shared.services.base_service import BaseService

@app.on_event("startup")
async def startup():
    logger.info(f"🚀 Starting {config.WORKER_ID}...")

    # ✅ MANDATORY: Register service heartbeat
    service = BaseService(config.WORKER_ID, logger=logger)
    asyncio.create_task(service.heartbeat())

    logger.info(f"✅ {config.WORKER_ID} started with heartbeat: state:service:{config.WORKER_ID}:available")
```

**What This Does:**

```
Startup:
  1. BaseService("my-service") created
  2. asyncio.create_task(service.heartbeat()) spawned (fire-and-forget)
  3. Service startup continues immediately

Background Loop (Every 20 seconds):
  1. service.heartbeat() refreshes Redis L1 key
  2. Key: state:service:my-service:available
  3. Value: {"port_opened": true|false|null, "timestamp": 1713085200.123}
     - port_opened: true if HTTP /health returns 200, false if down, null if no port
     - timestamp: Unix timestamp of heartbeat registration
  4. TTL: 60 seconds (3 × 20s interval)

If Service Crashes:
  1. Heartbeat loop stops
  2. Redis key expires after 60 seconds
  3. GateKeeper detects missing key
  4. Marks service as unavailable
```

**Real Examples from Production Services:**

**Ollama Service:**
```python
from canonical.shared.services.base_service import BaseService

@app.on_event("startup")
async def startup_event() -> None:
    global _http_client
    _http_client = httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT)

    # Fire-and-forget heartbeat
    service = BaseService("ollama", logger=logger)
    asyncio.create_task(service.heartbeat())
    logger.info("Ollama wrapper started: heartbeat=state:service:ollama:available")
```

**Stable Diffusion Service:**
```python
@app.on_event("startup")
async def startup() -> None:
    global _sd_client
    _sd_client = StableDiffusionClient(SD_API_URL)

    # Fire-and-forget heartbeat
    service = BaseService("stable-diffusion", logger=logger)
    asyncio.create_task(service.heartbeat())
    logger.info("SD wrapper started: heartbeat=state:service:stable-diffusion:available")
```

**Why Fire-and-Forget?**

- ✅ Service starts immediately (no blocking on Redis connection)
- ✅ Graceful degradation: if Redis unavailable, service still works
- ✅ Non-blocking: heartbeat runs in background, doesn't slow down request handling
- ✅ Production-safe: tested pattern used in Ollama, SD, GateKeeper

**Configuration:**

Heartbeat interval and TTL are configured in `config.py`:

```python
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))  # seconds (poll every 20s)
HEARTBEAT_TTL = HEARTBEAT_INTERVAL * 3  # TTL = 60s (3 × 20s interval)
# If not refreshed within TTL, key expires and service marked as unavailable
```

**Verification:**

Check if your service registered correctly:

```bash
redis-cli -h redis-local -p 6380 -a scarerunner
> KEYS "state:service:*"
state:service:ollama:available
state:service:stable-diffusion:available
state:service:my-service:available  # ← Your service should appear here
```

---

### Step 7: Create Tests

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

# tests/test_health.py
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

### Step 8: Create README.md

```markdown
# My Worker

## Overview

Brief description of what this worker does.

## Build & Run

```bash
docker-compose build
docker-compose up -d
```

## Health Check

```bash
curl http://localhost:8000/health
```

## Logs

```bash
docker-compose logs -f
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| WORKER_ID | my-worker-1 | Unique identifier |
| WORKER_PORT | 8000 | HTTP port |
| LOG_LEVEL | INFO | Logging level |

## Tests

```bash
pytest tests/
```
```

### Step 9: Verify the Implementation

Your worker is now ready for Launcher orchestration:

1. ✅ **Discoverable**: Located in `artifacts/canonical/worker/my-worker/`
2. ✅ **Deployable**: Has standalone `docker-compose.yml` with external network
3. ✅ **Health-checkable**: `GET /health` returns 200
4. ✅ **Configurable**: All config via environment variables
5. ✅ **Graceful**: Shuts down cleanly on SIGTERM
6. ✅ **Observable**: Comprehensive logging for debugging
7. ✅ **Testable**: Tests included with good coverage
8. ✅ **Documented**: README with setup and usage instructions

**Launcher will:**
- Discover your worker via `docker-compose.yml` path
- Start it: `docker-compose up -d`
- Monitor health: periodic `curl http://localhost:8000/health`
- Gracefully stop: send SIGTERM and wait for shutdown
- Restart on failure: based on docker-compose restart policy

---

---

## Internal Communication Port

**Job workers use different ports for Docker network communication:**

- **Standard job workers**: Port **8080** (Ollama, Stable Diffusion) or **9000** (Rembg) for internal Docker network
- **Internal (Docker network)**: `http://scareverse-{worker}-worker:{port}` - used by GateKeeper to dispatch jobs
- **No external exposure**: Job workers do NOT map ports to the host
- **Why different ports?**: Different workers have different conventions:
  - **Ollama + Stable Diffusion**: Use port 8080 (internal HTTP API)
  - **Rembg**: Uses port 9000 (legacy pattern)
  - Port 8000 is reserved for CentralHub (exposed via Nginx)
- **Configure via environment**: Set `WORKER_PORT` env var to override (default in config.py)

This design ensures:
- ✅ Clear separation: 8000 = external (CentralHub via Nginx), 8080/9000 = internal (workers)
- ✅ No port conflicts on the host
- ✅ GateKeeper routes to correct port per job-type configuration
- ✅ Each worker configurable, not forced to single port

**Recommended Ports by Worker Type:**
- Job processors (inference, image generation): **8080** (Ollama, SD) or **9000** (lightweight like Rembg)
- Storage workers (S3, Minio): **9001** or **9002** (if needing external access)
- Proxy workers (Nginx): **9003** or higher

---

## Job Types Definition (MANDATORY for All Workers)

**All workers must have a corresponding job-type JSON in `artifacts/canonical/job-types/`.**

Job types define what operations your worker handles and how GateKeeper orchestrates them. They're used by:
- **GateKeeper Orchestrator** → Routes jobs, selects resource thresholds based on `queue_type`
- **Backend** → Checks worker availability, decides L1 (owner) vs L2 (global) queue
- **Config** → `JOB_TYPES_CONFIG` loaded at startup, workers discovered dynamically

### Step 1: Create Job Type Definitions

Create JSON files in `artifacts/canonical/job-types/` for each operation your worker handles:

```bash
artifacts/canonical/job-types/
├── my_operation_v1.json      # Subprocess worker job type
└── my_operation_v2.json      # Another job type
```

**Example: `artifacts/canonical/job-types/my_operation_v1.json` (Subprocess Worker)**

```json
{
  "name": "my_operation_v1",
  "version": "1.0.0",
  "description": "Description of what this job type does",
  
  "queue_type": "cpu",
  "execution_model": "subprocess",
  
  "worker": {
    "type": "job",
    "path": "artifacts/canonical/workers/my-worker",
    "entry_point": "main.py",
    "python_version": "3.11+"
  },

  "queue": "scareverse:my-jobs:queue",
  "queue_l1": "scareverse:my-jobs:queue",
  "queue_l2": "scareverse:my-jobs:queue",
  "result_storage": "rpush_l1",
  "result_key_prefix": "scareverse:my-results",
  "result_key_ttl": 120,
  "timeout": 60,

  "dependencies": [],
  "aliases": ["my_operation_v1", "legacy_name_if_any"],
  
  "input_schema": {
    "type": "object",
    "required": ["data"],
    "properties": {
      "data": {"type": "string", "description": "Input data"}
    }
  },
  
  "output_schema": {
    "type": "object",
    "properties": {
      "result": {"type": "string", "description": "Processing result"}
    }
  }
}
```

**MANDATORY Fields:**
- `name`: Job type identifier (must match filename without .json)
- `queue_type`: **"cpu"** or **"gpu"** - Controls resource threshold in GateKeeper orchestrator
  - CPU: GateKeeper checks `ram_free > SCALE_UP_RAM_MIN_MB` before scaling
  - GPU: GateKeeper checks `vram_free > SCALE_UP_VRAM_MIN_MB` before scaling
- `execution_model`: **"subprocess"** (recommended for all new job workers)
- `worker.path`: Your worker folder path
- `queue_l1`: Owner-first queue name (fast, local Redis L1)
- `queue_l2`: Global queue fallback queue name
- `timeout`: Max execution time in seconds (60-300 typical)

**Recommended Fields:**
- `description`: Human-readable description
- `version`: Semantic versioning (1.0.0, etc)
- `dependencies`: List of long-running services this worker depends on (["ollama"] if calls Ollama)
- `aliases`: Legacy names for backwards compatibility
- `input_schema` / `output_schema`: JSON Schema for validation
- `result_storage`: Where to store results (always "rpush_l1" for now)
- `result_key_prefix`: Redis key prefix for results
- `result_key_ttl`: Result expiration in seconds (60-300 typical)

### Step 2: Reference Job Types in Worker Config

Update `config.py` to match the job type names:

```python
# Must match names in artifacts/canonical/job-types/*.json
SUPPORTED_JOB_TYPES = [
    "my_operation_v1",
    "my_operation_v2",
]
```

**Important:** Job type names must match the filenames (without .json)

### Step 3: Commit Job Types to Git

Job types are versionable artifacts, should be in git:

```bash
git add artifacts/canonical/job-types/
git commit -m "Add job type definitions for my-worker"
```

**Why Canonical?**
- ✅ System-level defaults (non-user-specific)
- ✅ Git-tracked (versioned with code)
- ✅ Discoverable by HybridDatabase
- ✅ Backend loads on startup for availability checks

**Can Override In:**
- `artifacts/runtime/job-types/` (dynamically generated at runtime)
- `artifacts/sandbox/{user-id}/job-types/` (user's local workers, if enabled)

---

## Optional: Integrating with GateKeeper for Job Dispatch

### When to Add This Section

**Only follow this section if:**
- ✅ Your worker processes **job requests** (atomic operations like image generation, text processing)
- ✅ You want **GateKeeper to dispatch** jobs to your worker via HTTP
- ✅ Your worker should be **discoverable** for owner-first scheduling (L1 before L2 jobs)

**Don't follow this section if:**
- ❌ Your worker is a **proxy or gateway** (Nginx, API layer)
- ❌ Your worker is **storage** (S3, Minio, databases)
- ❌ Your worker is **monitoring/logging** (metrics, dashboards)
- ❌ Your worker serves **direct HTTP requests** (not job-based)

### Pattern: Job Processing via HTTP + Heartbeat Registration

The GateKeeper integration pattern enables **stateless job dispatch**:
- **Worker Heartbeat**: Worker registers availability in Redis L1 (`state:worker:{job_type}:available`)
- **Job Dispatch**: GateKeeper polls L1/L2 queues, routes jobs via HTTP POST to worker `/process`
- **Result Storage**: GateKeeper persists results to Redis L1 after worker responds
- **Owner-First Scheduling**: Backend checks worker heartbeat before creating jobs (L1 vs L2 decision)

Your job worker will:
1. Publish heartbeat on startup: `state:worker:{job_type}:available`
2. Refresh heartbeat every 30s (TTL 60s)
3. Receive job requests: `POST /process` from GateKeeper
4. Process synchronously, return result in HTTP response
5. Delete heartbeat on shutdown
6. **DO NOT** touch Redis directly (GateKeeper handles result storage)

### Step 1: Understand the Complete Job Dispatch Flow

**System Architecture:**
```
Backend/Frontend
    ↓
[Check Worker Availability] state:worker:{job_type}:available
    ├─→ Key exists? → LPUSH L1 (owner-first queue)
    └─→ Key missing? → LPUSH L2 (global queue via CentralHub HTTP)
    ↓
GateKeeper (Orchestrator)
    ├─→ BRPOP L1 (1s timeout, owner jobs - fast)
    │   └─→ Found job? → Route to worker
    │
    └─→ BRPOP L2 (20s timeout, global jobs - fallback)
        └─→ Found job? → Route to worker
    ↓
HTTP POST to Worker
    ├─→ URL: http://scareverse-{worker-type}-worker:{port}/process
    ├─→ Body: {"job_id": "...", "input_data": {...}}
    ├─→ Response: {"success": true/false, "result": {...} or "error": "..."}
    ↓
Result Persistence (GateKeeper Responsibility)
    ├─→ For rpush_l1 jobs: RPUSH to scareverse:{job_type}-results:{job_id}
    ├─→ For hset_l2 jobs: HSET state:job:{job_id} (not currently used)
    ├─→ TTL: Configured per job-type (60-300s typical)
    ↓
Backend Retrieval
    └─→ BRPOP from result queue (blocking)
        └─→ Receives result, passes to Frontend
```

**Worker Heartbeat (Availability Signaling):**
- Worker publishes `state:worker:{job_type}:available` to Redis L1 on startup
- Value: `{"worker_id": "...", "service": "...", "job_types": [...], "timestamp": "..."}`
- TTL: 60s (3 × HEARTBEAT_INTERVAL where interval = 20s default)
- Refreshed every HEARTBEAT_INTERVAL (20s) via background loop
- Backend checks this key to decide: **L1 queue (fast, owner)** or **L2 queue (global, fallback)**

**Job Dispatch (HTTP via GateKeeper):**
1. Backend creates job, checks `state:worker:{job_type}:available` key
2. If key exists: Job pushed to L1 queue → GateKeeper delivers fast (owner-first)
3. If key missing: Job pushed to L2 queue → GateKeeper delivers eventually (global)
4. GateKeeper: `POST http://scareverse-{worker-type}-worker:{port}/process` with job_data
5. Worker processes **synchronously**, returns result in HTTP response (HTTP 200 or 500)
6. GateKeeper does NOT re-queue job if worker times out (timeout is job-type config)

**Result Storage (GateKeeper Responsibility):**
- Worker does NOT persist results
- GateKeeper receives HTTP response and stores in Redis L1
- Key: `scareverse:{result_key_prefix}:{job_id}` (format from job-type JSON)
- Example: `scareverse:ollama-results:job-abc-123`
- TTL: Configured in job-type JSON (60-300s typical)
- Backend retrieves: `BRPOP from scareverse:*-results:*` (blocking, predictable)

### Step 2: Add Redis Configuration (Heartbeat Only)

Update `config.py` (add to existing config):

```python
# Redis L1 (Local heartbeat registration only)
# Workers use this ONLY to publish availability
REDIS_L1_HOST = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_PASSWORD = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
REDIS_L1_DB = int(os.getenv("REDIS_L1_DB", "0"))

# Job types this worker handles
# Must match names in artifacts/canonical/job-types/*.json files
SUPPORTED_JOB_TYPES = [
    "my_operation_v1",
    "my_operation_v2",
]

# Heartbeat configuration (real implementation)
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))  # seconds (poll every 20s)
HEARTBEAT_TTL = HEARTBEAT_INTERVAL * 3  # TTL = 60s (3 × 20s interval)
# If not refreshed within TTL, key expires and worker marked as unavailable
# Backend uses presence of state:worker:{job_type}:available key to decide L1 vs L2 queue

# Internal port (8000 default, 8080 for inference, 9000 for lightweight)
WORKER_PORT = int(os.getenv("WORKER_PORT", "8000"))
```

**Heartbeat Pattern (Real Implementation):**
```
Startup:
  └→ await _init_redis_l1()
  └→ await _publish_availability(redis_client)  # Register immediately
  └→ asyncio.create_task(_heartbeat_loop(redis_client))

Every HEARTBEAT_INTERVAL (20s):
  └→ await _publish_availability(redis_client)  # Refresh key with new TTL

Shutdown:
  └→ _shutdown_event.set()
  └→ _heartbeat_task.cancel()
  └→ await redis_client.delete(f"state:worker:{job_type}:available")  # Unregister
  └→ await redis_client.close()
```

**Why TTL = 3× Interval:**
- Refresh every 20s → TTL 60s (3 × 20s)
- If 1-2 refreshes miss → key expires (worker marked unavailable)
- Prevents stale workers from accepting jobs

**Important:** Workers do NOT access Redis L2 or use BRPOP. Only publish heartbeat to L1.

### Step 3: Add Heartbeat Registration + Job Processing Endpoint

Update `main.py`:

```python
import asyncio
import json
import redis.asyncio as aioredis
from datetime import datetime, timezone
from pydantic import BaseModel

_redis_l1: Optional[aioredis.Redis] = None
_heartbeat_task: Optional[asyncio.Task] = None
_shutdown_event = asyncio.Event()

# ============================================================================
# Models
# ============================================================================

class ProcessRequest(BaseModel):
    job_id: str
    input_data: dict

class ProcessResponse(BaseModel):
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None

# ============================================================================
# Redis L1 Connection (for heartbeat only)
# ============================================================================

async def _init_redis_l1():
    """Initialize async Redis L1 client (for heartbeat registration only)"""
    try:
        client = aioredis.Redis(
            host=config.REDIS_L1_HOST,
            port=config.REDIS_L1_PORT,
            db=config.REDIS_L1_DB,
            password=config.REDIS_L1_PASSWORD,
            decode_responses=True,
        )
        await client.ping()
        logger.info(f"✅ Redis L1 connected for heartbeat")
        return client
    except Exception as e:
        logger.warning(f"⚠️ Redis L1 connection failed: {e} – worker will start without heartbeat")
        return None

# ============================================================================
# Heartbeat Registration (Availability Signaling)
# ============================================================================

async def _publish_availability(redis_client: aioredis.Redis):
    """Register worker availability in Redis L1 for all supported job types"""
    for job_type in config.SUPPORTED_JOB_TYPES:
        key = f"state:worker:{job_type}:available"
        payload = json.dumps({
            "worker_id": config.WORKER_ID,
            "job_type": job_type,
            "node": "local",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await redis_client.setex(
            key,
            ex=config.HEARTBEAT_TTL,
            value=payload
        )

async def _heartbeat_loop(redis_client: aioredis.Redis):
    """Periodically refresh worker availability in Redis L1"""
    while not _shutdown_event.is_set():
        try:
            if redis_client:
                await _publish_availability(redis_client)
                logger.debug(f"Heartbeat refreshed for {len(config.SUPPORTED_JOB_TYPES)} job types")
        except Exception as e:
            logger.warning(f"Heartbeat publish failed: {e}")
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)

# ============================================================================
# Job Processing
# ============================================================================

async def _process_job(input_data: dict) -> dict:
    """
    Execute the job synchronously.

    YOUR BUSINESS LOGIC HERE
    Return dict with result or raise exception.
    """
    logger.info(f"Processing job: {input_data}")

    try:
        # Example: echo input
        result = {
            "processed": True,
            "input": input_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result
    except Exception as e:
        logger.error(f"Job processing failed: {e}", exc_info=True)
        raise

# ============================================================================
# HTTP Endpoints
# ============================================================================

@app.post("/process", response_model=ProcessResponse)
async def process_job(request: ProcessRequest) -> ProcessResponse:
    """
    Process a job synchronously.

    Called by GateKeeper with job_id and input_data.
    Return result or error in HTTP response.
    GateKeeper persists result to Redis L1.
    """
    try:
        logger.info(f"[JOB] Processing {request.job_id}")
        result = await _process_job(request.input_data)
        logger.info(f"[JOB] ✅ {request.job_id} completed")
        return ProcessResponse(success=True, result=result)
    except Exception as e:
        logger.error(f"[JOB] ❌ {request.job_id} failed: {e}")
        return ProcessResponse(success=False, error=str(e))

@app.on_event("startup")
async def startup():
    global _redis_l1, _heartbeat_task

    logger.info(f"🚀 Starting {config.WORKER_ID}...")

    # Initialize Redis L1 for heartbeat (optional, graceful if fails)
    _redis_l1 = await _init_redis_l1()

    if _redis_l1:
        # Register availability and start heartbeat
        try:
            await _publish_availability(_redis_l1)
            logger.info(f"✅ Worker availability registered for job types: {config.SUPPORTED_JOB_TYPES}")
        except Exception as e:
            logger.warning(f"Initial availability registration failed: {e}")

        # Start heartbeat refresh loop
        _heartbeat_task = asyncio.create_task(_heartbeat_loop(_redis_l1))
    else:
        logger.warning("⚠️ Worker will run without heartbeat (no worker availability signaling)")

    logger.info("✅ Worker started – waiting for job requests on POST /process")

@app.on_event("shutdown")
async def shutdown():
    """Graceful shutdown: signal handler + cleanup."""
    logger.info("🛑 Shutting down...")
    _shutdown_event.set()  # Signal background tasks to stop

    # Cancel heartbeat loop
    if _heartbeat_task:
        _heartbeat_task.cancel()
        try:
            await _heartbeat_task
        except asyncio.CancelledError:
            pass  # Expected when cancelling

    # Unregister availability from Redis L1
    if _redis_l1:
        try:
            for job_type in config.SUPPORTED_JOB_TYPES:
                await _redis_l1.delete(f"state:worker:{job_type}:available")
            await _redis_l1.close()
            logger.info("✅ Availability unregistered, Redis closed")
        except Exception as e:
            logger.warning(f"Shutdown cleanup failed: {e}")

    logger.info("✅ Shutdown complete")
```

**Graceful Shutdown in main (for signal handling):**

```python
# main.py - Add signal handler for SIGTERM/SIGINT
import signal
import asyncio

_shutdown_event = asyncio.Event()

def _handle_signal(signum, frame):
    """Signal handler for SIGTERM/SIGINT."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    _shutdown_event.set()

# Register handlers BEFORE running uvicorn
signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=config.WORKER_PORT, log_level=config.LOG_LEVEL.lower())
```
```

### Step 4: Update docker-compose.yml

Add Redis environment variables (no `ports:` for job workers):

```yaml
    environment:
      # ... existing vars ...

      # Redis L1 (local/owner)
      REDIS_L1_HOST: ${REDIS_L1_HOST:-redis-local}
      REDIS_L1_PORT: ${REDIS_L1_PORT:-6380}
      REDIS_L1_PASSWORD: ${REDIS_L1_PASSWORD:-scarerunner}
      REDIS_L1_DB: ${REDIS_L1_DB:-0}

      # Redis L2 (global)
      REDIS_L2_HOST: ${REDIS_L2_HOST:-host.docker.internal}
      REDIS_L2_PORT: ${REDIS_L2_PORT:-6379}
      REDIS_L2_DB: ${REDIS_L2_DB:-0}

    # No ports: exposed - job workers communicate via Docker network on port 9000
    # GateKeeper reaches this worker at: http://my-worker:9000
```

### Step 5: Job Loop Best Practices

```python
# ✅ CORRECT: Owner-first scheduling
result_l1 = await redis_l1.brpop(queue_l1, timeout=1)   # 1s non-blocking
if result_l1 is None:
    result_l2 = await redis_l2.brpop(queue_l2, timeout=20)  # 20s blocking

# ✅ CORRECT: Store results with TTL
await redis_l2.hset(result_key, mapping=result_data)
await redis_l2.expire(result_key, 3600)

# ✅ CORRECT: Graceful shutdown
while not _shutdown_event.is_set():
    # ... job processing ...
```

---

## How GateKeeper Routes Jobs to Your Worker

**Critical Understanding:**

GateKeeper uses these fields from your job-type JSON to route jobs:

```json
{
  "name": "my_operation_v1",
  "endpoint": "http://scareverse-my-worker-worker:8080",  // ← GateKeeper makes HTTP POST here
  "queue_l1": "scareverse:cpu-jobs:queue",                // ← BRPOP source (1s timeout)
  "queue_l2": "scareverse:cpu-jobs:queue",                // ← BRPOP source (20s timeout)
  "result_storage": "rpush_l1",                           // ← Where to store results
  "result_key_prefix": "scareverse:my_operation-results", // ← Result key pattern
  "result_key_ttl": 120,                                  // ← Result expiration
  "timeout": 60                                           // ← Max execution time
}
```

**Routing Flow:**

1. **Job Created**: Backend/Frontend calls job creation with `job_type: "my_operation_v1"`
2. **Availability Check**: Backend checks Redis L1 key `state:worker:my_operation_v1:available`
   - **If exists**: Push to `scareverse:cpu-jobs:queue` (L1)
   - **If missing**: Push to `scareverse:cpu-jobs:queue` via HTTP (L2)
3. **GateKeeper Polls**:
   - `BRPOP scareverse:cpu-jobs:queue 1` → owner jobs (fast)
   - If no jobs: `BRPOP scareverse:cpu-jobs:queue 20` → global jobs (fallback)
4. **GateKeeper Dispatches**:
   - Looks up job-type in database
   - Finds `endpoint: http://scareverse-my-worker-worker:8080`
   - `POST /process` with job data
5. **Worker Processes**: Runs synchronously, returns result in HTTP response
6. **GateKeeper Stores Result**:
   - Key: `scareverse:my_operation-results:{job_id}`
   - Value: JSON result from worker
   - TTL: 120s (from job-type config)
7. **Backend Retrieves**: `BRPOP scareverse:my_operation-results:*` blocking until available

**Must-Have Configuration:**

For routing to work, ensure:
- ✅ Job-type JSON has correct `endpoint` (matches your container name format)
- ✅ Your container name is `scareverse-{worker-type}-worker`
- ✅ Your WORKER_PORT matches the port in `endpoint` URL
- ✅ You publish heartbeat to Redis L1 for owner-first scheduling
- ✅ Your `/process` endpoint accepts `{"job_id": "...", "input_data": {...}}`
- ✅ Your `/process` endpoint returns `{"success": bool, "result": dict or "error": str}`

**If routing fails:**
- ❌ Check container name: `docker ps | grep scareverse`
- ❌ Check health endpoint: `curl http://container:port/health`
- ❌ Check Redis L1 heartbeat: `redis-cli -h redis-local -p 6380 keys "state:worker:*"`
- ❌ Check GateKeeper logs for dispatch errors

---

## Verification Checklist

Before submitting a worker:

**Core Requirements (Subprocess Workers):**
- [ ] Located in `artifacts/canonical/workers/{name}/`
- [ ] `worker.py` implements `BaseWorker.execute()` (no FastAPI/HTTP)
- [ ] `main.py` is a CLI entry point (reads stdin JSON, writes stdout JSON)
- [ ] `requirements.txt` lists execution dependencies only (no fastapi/uvicorn)
- [ ] Job-type JSON at `artifacts/canonical/job-types/{name}.json` with `execution_model: "subprocess"`
- [ ] All config via environment variables or job input (no hardcoding)
- [ ] Comprehensive logging to stderr (stdout is reserved for JSON result)
- [ ] Tests with >80% coverage
- [ ] Self-contained (can be used by a fresh GateKeeper instance without configuration)

**Core Requirements (Service Workers — Docker only):**
- [ ] Located in `artifacts/canonical/services/{name}/`
- [ ] Dockerfile is Python 3.11-slim with minimal dependencies
- [ ] docker-compose.yml uses external `scareverse-net`
- [ ] All config via environment variables (no hardcoding)
- [ ] `/health` endpoint returns 200
- [ ] Graceful shutdown on SIGTERM/SIGINT
- [ ] Comprehensive logging (DEBUG, INFO, ERROR)
- [ ] Tests with >80% coverage
- [ ] README.md with setup, config table, and usage examples
- [ ] Self-contained (can be deployed independently)

**Optional: GateKeeper Integration (Job Workers Only):**

Only complete this if your worker should receive jobs from GateKeeper:

- [ ] Reads from Redis L1 first (1s timeout - owner jobs)
- [ ] Falls back to Redis L2 (20s timeout - global jobs)
- [ ] Stores results in Redis L2 with TTL
- [ ] Handles job errors properly and logs them
- [ ] Tests for job loop (including L1/L2 fallback)
- [ ] README documents job input/output schema
- [ ] Graceful handling of Redis connection failures

---

## Directory Structure

```
my-worker/
├── main.py                    # REQUIRED: Entry point
├── config.py                  # REQUIRED: Configuration
├── Dockerfile                 # REQUIRED: Container image
├── docker-compose.yml         # REQUIRED: Standalone deployment
├── requirements.txt           # REQUIRED: Dependencies
├── tests/                     # REQUIRED: Tests
│   ├── conftest.py
│   ├── test_health.py
│   └── test_job_loop.py       # OPTIONAL: If GateKeeper integration
├── README.md                  # REQUIRED: Documentation
└── utils.py                   # OPTIONAL: Helper functions
```

---

## Real Implementations (Source of Truth)

These are the working workers in production. Use them as reference:

### Subprocess Workers (Recommended for new job workers)

| Worker | Path | Purpose | Execution |
|--------|------|---------|-----------|
| **Rembg** | `artifacts/canonical/workers/rembg/` | Background removal | subprocess |
| **Ollama-wrapper** | `artifacts/canonical/workers/ollama-wrapper/` | LLM inference wrapper | subprocess |
| **SD-wrapper** | `artifacts/canonical/workers/stable-diffusion-wrapper/` | Image generation wrapper | subprocess |
| **TEMPLATE** | `artifacts/canonical/workers/TEMPLATE/` | Boilerplate for new workers | — |

### Service Workers (Long-lived Docker containers)

| Worker | Path | Purpose | Port |
|--------|------|---------|------|
| **GateKeeper** | `artifacts/canonical/services/gatekeeper/` | Job dispatcher/orchestrator | 8000 |
| **Ollama** | `artifacts/canonical/services/ollama/` | LLM inference service | 8080 |
| **Stable Diffusion** | `artifacts/canonical/services/stable-diffusion/` | Image generation service | 9090 |

**What to learn from each:**

1. **TEMPLATE** (`artifacts/canonical/workers/TEMPLATE/worker.py`):
   - Minimal `BaseWorker` subclass structure
   - CLI entry point pattern in `main.py`
   - Test scaffold

2. **Rembg** (`artifacts/canonical/workers/rembg/worker.py`):
   - Model loading in `setup()` / cleanup in `teardown()`
   - Base64 image processing in `execute()`
   - Dependency isolation via `.venv/`

3. **GateKeeper** (`artifacts/canonical/services/gatekeeper/main.py`):
   - SIGTERM/SIGINT signal handling pattern
   - Background job loop with L1→L2 fallback
   - Worker discovery and venv management

---

## Debugging & Troubleshooting

**Problem: GateKeeper not routing jobs to my worker**

Check in order:

1. **Container name format** (CRITICAL):
   ```bash
   docker ps | grep scareverse
   # Must see: scareverse-{worker-type}-worker
   # If not: Update container_name in docker-compose.yml
   ```

2. **Health endpoint**:
   ```bash
   curl http://scareverse-my-worker-worker:8080/health
   # Must return 200 with {"status": "ok"} or {"status": "healthy"}
   # If fails: Check WORKER_PORT env var, check logs
   ```

3. **Redis L1 heartbeat**:
   ```bash
   redis-cli -h redis-local -p 6380
   > KEYS "state:worker:*"
   # Must see: state:worker:my_operation_v1:available
   # If missing: Check REDIS_L1_* env vars, check logs for connection errors
   ```

4. **Job-type JSON endpoint**:
   ```bash
   # In artifacts/canonical/job-types/my_operation_v1.json
   # Must have: "endpoint": "http://scareverse-my-worker-worker:8080"
   # Matches container name and port exactly
   ```

5. **GateKeeper logs**:
   ```bash
   docker logs scareverse-gatekeeper-worker
   # Search for: "dispatching", "worker", "my_operation"
   # Look for: "[job_id] dispatching to http://scareverse-..."
   ```

**Problem: Worker starts but heartbeat not published**

Check:
1. REDIS_L1_HOST, REDIS_L1_PORT, REDIS_L1_PASSWORD env vars set correctly
2. Redis L1 container running: `docker ps | grep redis-local`
3. Network connectivity: `docker exec {worker} curl http://redis-local:6380/`
4. SUPPORTED_JOB_TYPES matches job-type JSON names exactly

**Problem: Worker receives job but errors on processing**

Check:
1. Worker logs: `docker logs scareverse-my-worker-worker`
2. Input data format: `POST /process` must send `{"job_id": "...", "input_data": {...}}`
3. Response format: Must return `{"success": bool, "result": dict}` or `{"success": false, "error": str}`
4. Timeout: Ensure processing completes within job-type `timeout` (60-300s typical)

**Problem: Result not stored in Redis**

Check:
1. Worker responds with HTTP 200: `docker logs scareverse-gatekeeper-worker`
2. Job-type has `result_storage: "rpush_l1"` (all current implementations use this)
3. Result key pattern: `scareverse:{result_key_prefix}:{job_id}` in job-type JSON
4. TTL: Result should expire after configured `result_key_ttl` seconds

---

## Quick Start (Summary)

### Subprocess Worker (recommended for new job workers)

**1. Copy template:**
```bash
cp -r artifacts/canonical/workers/TEMPLATE artifacts/canonical/workers/my-worker
```

**2. Implement `worker.py`:**
```python
from canonical.shared.base_worker import BaseWorker

class MyWorker(BaseWorker):
    def execute(self) -> dict:
        return {"output": process(self.input_data)}
```

**3. Create job-type JSON** (`artifacts/canonical/job-types/my_operation.json`):
```json
{
  "name": "my_operation",
  "execution_model": "subprocess",
  "worker": {"path": "artifacts/canonical/workers/my-worker"},
  "configuration": {"timeout_seconds": 60},
  "queue_l1": "scareverse:cpu-jobs:queue",
  "result_storage": "rpush_l1",
  "result_key_prefix": "scareverse:my-results",
  "result_key_ttl": 120
}
```

**4. Test:**
```bash
pytest artifacts/canonical/workers/my-worker/tests/
```

**5. Deploy (automatic):** Restart GateKeeper — it auto-discovers and runs the worker.

---

### Service Worker (long-lived Docker container)

**1. Create directory:**
```bash
mkdir -p artifacts/canonical/services/my-worker
```

**2. Create minimal files:**
- `Dockerfile` (Python 3.11-slim, EXPOSE 8000)
- `docker-compose.yml` (scareverse-net external, health check)
- `config.py` (LOG_LEVEL, WORKER_ID, WORKER_PORT from env)
- `main.py` (FastAPI app, GET /health endpoint)
- `requirements.txt` (fastapi, uvicorn, pydantic)

**3. Create job-type JSON** with `execution_model: "service"` and `service.endpoint`.

**4. Test:**
```bash
docker-compose up -d
curl http://localhost:8000/health
```

---

**Last Updated**: 2026-03-10
**Version**: 4.0.0 (Phase 4: Subprocess workers primary model, service workers for long-lived infrastructure)
**Versioning**: Major version tracks architecture phase (v1=Phase1 HTTP, v2=Phase2 subprocess, v4=Phase4 production-ready)
**Source of Truth**: `artifacts/canonical/workers/` (subprocess) and `artifacts/canonical/services/` (service Docker containers)

---

## Phase 2: Subprocess Workers (New in v2.1)

In Phase 2, a new execution model was introduced: **subprocess workers**.
These are lightweight Python scripts that GateKeeper spawns as isolated
subprocesses instead of calling via HTTP.

### When to Use Subprocess Workers

| Model | Use When |
|-------|----------|
| **service** (HTTP) | Long-lived service with GPU/memory, always running (Ollama, SD) |
| **subprocess** | Ephemeral CPU jobs, batch processing, no persistent state needed (Rembg) |

### Subprocess Worker Structure

```
artifacts/canonical/workers/         ← New directory (Phase 2)
└── your-worker/
    ├── main.py                       # REQUIRED: CLI entry point
    ├── worker.py                     # REQUIRED: BaseWorker subclass
    ├── requirements.txt              # REQUIRED: Dependencies (venv auto-created)
    ├── .gitignore                    # REQUIRED: Ignore .venv/, __pycache__/
    ├── __init__.py
    └── tests/
        ├── __init__.py
        └── test_worker.py
```

> **Template:** Copy from `artifacts/canonical/workers/TEMPLATE/`

### Subprocess Communication Contract

```
GateKeeper → subprocess stdin (JSON):
{
  "job_id": "uuid-here",
  "job_type": "your_job_type",
  "input_data": { ...arbitrary dict... }
}

subprocess → GateKeeper stdout (JSON):
{"success": true, "result": { ...output dict... }}   ← success
{"success": false, "error": "error message"}          ← failure
```

⚠️ **All logging must go to stderr** – stdout is reserved for the JSON result.

### Step-by-Step: Create a Subprocess Worker

**1. Copy the template:**
```bash
cp -r artifacts/canonical/workers/TEMPLATE artifacts/canonical/workers/my-worker
```

**2. Implement `worker.py`:**
```python
from canonical.shared.base_worker import BaseWorker

class MyWorker(BaseWorker):
    def setup(self):
        # Load model once
        pass

    def execute(self):
        # Process self.input_data, return result dict
        return {"output": "processed"}

    def teardown(self):
        # Release resources
        pass
```

**3. Update `main.py`** (usually no changes needed from template).

**4. Create `job-types/my_job_type.json`:**
```json
{
  "name": "my_job_type",
  "execution_model": "subprocess",
  "worker": {
    "path": "artifacts/canonical/workers/my-worker",
    "entry_point": "main.py"
  },
  "configuration": {
    "timeout_seconds": 60
  },
  "result_storage": "rpush_l1",
  "result_key_prefix": "scareverse:my-results",
  "result_key_ttl": 3600,
  "queue": "cpu-jobs"
}
```

**5. Worker Discovery (automatic):**

GateKeeper automatically discovers all workers on startup via `WorkerDiscovery`.
No registration step required – the worker is available as soon as its directory
exists in `artifacts/canonical/workers/` with a valid `main.py`.

### Venv Auto-Setup

GateKeeper **automatically creates a `.venv/`** inside each worker directory on
the first job execution:

1. `python3 -m venv .venv/` is run
2. `pip install -r requirements.txt` is run (if requirements.txt exists)
3. `.venv/bin/python` is cached for subsequent calls

The `.venv/` is **not recreated** if it already exists. To force a rebuild:
```python
from job_executor import invalidate_venv_cache
invalidate_venv_cache("my-worker")  # Next job triggers rebuild
```

### Testing Subprocess Workers

Subprocess workers are tested by writing a fake `main.py` that mimics the
real worker, then invoking `WorkerExecutor` directly:

```python
import pytest
from canonical.shared.worker_executor import WorkerExecutor
import sys

@pytest.mark.asyncio
async def test_my_worker_success(tmp_path):
    worker_dir = tmp_path / "workers" / "my-worker"
    worker_dir.mkdir(parents=True)
    (worker_dir / "main.py").write_text(
        "import json, sys\n"
        "data = json.loads(sys.stdin.read())\n"
        "print(json.dumps({'success': True, 'result': {'done': True}}))\n"
    )

    executor = WorkerExecutor(workers_path=str(tmp_path / "workers"))
    executor._venv_ready["my-worker"] = Path(sys.executable)

    result = await executor.execute(
        job_type="my_job_type",
        job_id="test-001",
        input_data={},
        worker_config={
            "worker": {"path": "artifacts/canonical/workers/my-worker"},
            "configuration": {"timeout_seconds": 10},
        },
    )
    assert result["done"] is True
```

See `tests/test_integration_rembg.py` for more examples.

---
