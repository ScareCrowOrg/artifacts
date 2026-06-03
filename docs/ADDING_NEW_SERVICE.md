---
title: Adding New Service Workers
description: Complete guide for creating long-lived infrastructure services (Traefik, Cloudflared, Redis, Backend)
version: 1.0.0
updated: 2026-04-14
processed: true
processed_date: 2026-04-24
themes:
  - infrastructure
  - services
  - development-guide
modules:
  - infrastructure
code_verified: true
dead_docs_found: false
---


# Adding New Service Workers (Infrastructure Services Only)

## ⚠️ Important: This Guide is for Infrastructure Services, NOT Job Workers

**DO NOT use this guide for job workers.** See **ADDING_NEW_WORKER.md** instead.

| Type | Guide | Examples | Execution |
|------|-------|----------|-----------|
| **Job Workers** (recommended) | ADDING_NEW_WORKER.md | Rembg, OllamaWorker, SDWorker | Subprocess (`execution_model: "subprocess"`) |
| **Infrastructure Services** | THIS GUIDE | Traefik, Cloudflared, Redis, Backend | Docker container (long-lived) |

**This guide is ONLY for long-lived infrastructure services.**

---

## Definition

**A Service is a long-lived Docker container that provides infrastructure or API capabilities.**

Services are deployed via **Launcher** and registered in Redis L1 via heartbeat. They're discovered by GateKeeper for health monitoring and by Workers for HTTP calls.

**Examples:** 
- **Infrastructure**: Traefik, Cloudflared, Redis, MongoDB
- **AI Services**: Ollama, Stable Diffusion, InstantMesh
- **Application**: Backend, Auth-Proxy, Vite

**Note**: Ollama, SD, InstantMesh are implemented as:
1. **Service** (long-lived Docker container) - registered in Redis heartbeat
2. **Wrapper Worker** (subprocess) - OllamaWorker, SDWorker, InstantMeshWorker call the service via HTTP

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│            Long-Lived Infrastructure Service             │
│                                                          │
│  ✅ Dockerfile (Alpine or language-native)               │
│  ✅ docker-compose.yml (external network)                │
│  ✅ BaseService heartbeat (Redis L1 registration)        │
│  ✅ Graceful shutdown (SIGTERM)                          │
│  ✅ Deployable via Launcher                              │
│  ✅ Called by Wrapper Workers via HTTP (optional)        │
└──────────────────────────────────────────────────────────┘
        │
        ├─ HTTP/API Services 
        │  ├─ Backend (FastAPI + uvicorn + heartbeat)
        │  ├─ Ollama Service (wrapper runs in container)
        │  ├─ Stable Diffusion Service (inference service)
        │  └─ Auth-Proxy (middleware + heartbeat)
        │
        └─ Infrastructure Services (Native Tools)
           ├─ Traefik (native binary + Python heartbeat)
           ├─ Cloudflared (native tunnel + Python heartbeat)
           ├─ Redis (native server + Python heartbeat)
           └─ MongoDB, Postgres (databases + heartbeat)
```

**Key Insight**: Services can be:

1. **Called by Workers** (service-dependent workers):
   - **OllamaWorker** (subprocess) → calls `http://scareverse-ollama-service:11434/api/generate`
   - **StableDiffusionWorker** (subprocess) → calls `http://scareverse-sd-service:9090/api/generate`

2. **Standalone Infrastructure** (no workers call them):
   - **Traefik** → API gateway (routing, load balancing) - used by Launcher/GateKeeper directly
   - **Cloudflared** → Tunnel to external network - used by system infrastructure
   - **Redis** → In-memory store - used by all components (GateKeeper, Backend, Workers)
   - **MongoDB** → Database - used by CentralHub (Backend)
   - **Auth-Proxy** → Authentication middleware - used by frontend requests

All services follow the same pattern: **Dockerfile + docker-compose.yml + heartbeat registration**.

---

## Service Types: Job-Dependent vs Standalone

### Job-Dependent Services
Services that are called by Wrapper Workers (subprocess). Example:
- **Ollama Service** → Called by OllamaWorker via `http://scareverse-ollama-service:11434/api/generate`
- **Stable Diffusion Service** → Called by SDWorker via `http://scareverse-sd-service:9090/api/generate`
- **InstantMesh Service** → Called by InstantMeshWorker via `http://scareverse-worker-instantmesh:8000/process`

### Standalone Services
Infrastructure services that provide capabilities to the system. Workers don't call them; they're used directly by Launcher, GateKeeper, Backend, or frontend. Examples:
- **Traefik** (`artifacts/canonical/services/traefik/`)
  - API gateway for routing requests
  - Used by: Launcher (service discovery), Frontend (HTTP routing)
  - Not called by workers; system infrastructure
  
- **Cloudflared** (`artifacts/canonical/services/cloudflared/`)
  - Tunnel to external network (Cloudflare)
  - Used by: System infrastructure
  - Not called by workers; handles outbound connectivity
  
- **Redis** (`artifacts/canonical/services/redis/`)
  - In-memory store for queues, state, heartbeats
  - Used by: GateKeeper, Workers, Backend, CentralHub
  - Not called by workers; foundational infrastructure
  
- **Auth-Proxy** (`artifacts/canonical/services/auth-proxy/`)
  - Authentication middleware
  - Used by: Frontend requests (via Traefik)
  - Not called by workers; middleware layer

**Both types follow the same implementation pattern** (Dockerfile, docker-compose.yml, heartbeat registration). The difference is in how they're used by the system.

---

## 🚨 MANDATORY REQUIREMENTS CHECKLIST

- [ ] **Self-contained folder** - `artifacts/canonical/services/{name}/`
- [ ] **Dockerfile** - Alpine-based or language-native (Python 3.11-slim for Python services)
- [ ] **docker-compose.yml** - Standalone, uses `scareverse-net` external network
- [ ] **requirements.txt** - Python dependencies (if Python-based; skip if using native tool)
- [ ] **main.py or entrypoint.sh** - Entry point with proper logging (language-appropriate)
- [ ] **config.py** - Configuration via environment variables (if needed; optional for non-Python services)
- [ ] **🚨 MANDATORY: Redis L1 Heartbeat Registration** - `BaseService(name).heartbeat()` on startup
  - **Heartbeat pattern options**:
    - **Fire-and-forget (FastAPI services)**: `asyncio.create_task(service.heartbeat())` in startup event (e.g., Backend, Ollama)
    - **Blocking foreground (non-HTTP services)**: `await service.heartbeat()` in main loop (e.g., Cloudflared waits in PID 1) 
    - **Choose based on service type**: FastAPI → fire-and-forget; native tool → blocking
  - Registers key: `state:service:{service-name}:available` in Redis L1
  - Background task refreshes every HEARTBEAT_INTERVAL (default: 20s)
  - Heartbeat CHECKS `/health` endpoint if service_port is configured (port health validation)
  - If no port configured (non-HTTP services), `port_opened: null` (no health check possible)
  - See: "Service Heartbeat Registration" section below
- [ ] **Graceful shutdown** - Handles SIGTERM/SIGINT properly
- [ ] **Comprehensive logging** - DEBUG, INFO, ERROR levels
- [ ] **Tests** - Unit + integration tests, >80% coverage
- [ ] **README.md** - Setup, configuration, usage examples

**If your service doesn't meet these, it will be rejected.**

**🚨 NOTE: Heartbeat registration is NON-NEGOTIABLE.** All service workers in production (Backend, Traefik, Cloudflared) use this pattern. Your service MUST implement it.

---

## Core Implementation

### Step 1: Create Service Directory

```bash
# For service workers:
mkdir -p artifacts/canonical/services/my-service
cd artifacts/canonical/services/my-service
```

---

### Step 2: Create Dockerfile

**Requirements:**

**For Python services:**
- ✅ `python:3.11-slim` base image (or `python:3.11-alpine` for minimal footprint)
- ✅ Copy requirements.txt, pip install
- ✅ Copy Python source code

**For non-Python services:**
- ✅ Language-native base: `traefik:v3.1.0`, `node:20-alpine`, `redis:7-alpine`, etc.
- ✅ Copy language-specific config/code (varies by tool)
- ✅ No requirements.txt needed

**For all services:**
- ✅ Minimal system dependencies (only what's needed)
- ✅ Use Alpine when possible (smaller images)
- ✅ EXPOSE port (if applicable)
- ✅ ENTRYPOINT or CMD with graceful shutdown

**Example (Traefik - non-Python service):**
```dockerfile
FROM traefik:v3.1.0

WORKDIR /app

# Install Python for heartbeat
RUN apk add --no-cache python3 py3-pip gcc musl-dev python3-dev
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt
RUN apk del gcc musl-dev python3-dev

# Service config
COPY traefik.yml /app/traefik.yml
COPY heartbeat.py /app/heartbeat.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN mkdir -p /app/logs

EXPOSE 80 8080

ENTRYPOINT ["/app/entrypoint.sh"]
```

**Example (FastAPI - Python service):**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py config.py ./

EXPOSE 5050

CMD ["python", "main.py"]
```

---

### Step 3: Create docker-compose.yml

**Requirements:**
- ✅ External network: `scareverse-net` (required for Launcher routing)
- ✅ All config via environment variables
- ✅ No healthcheck section (use BaseService heartbeat instead)
- ✅ Graceful shutdown (stop_grace_period)

```yaml
services:
  my-service:
    build:
      context: ../../../..
      dockerfile: artifacts/canonical/services/my-service/Dockerfile
    image: localhost:5001/scareverse-my-service:staging
    container_name: scareverse-my-service

    environment:
      # ── Logging ────────────────────────────────────────────────────────────
      LOG_LEVEL: ${LOG_LEVEL:-INFO}

      # ── Service identification ────────────────────────────────────────────
      WORKER_ID: ${WORKER_ID:-my-service}

      # ── Redis / heartbeat ──────────────────────────────────────────────────
      REDIS_L1_HOST: ${REDIS_L1_HOST:-redis-local}
      REDIS_L1_PORT: ${REDIS_L1_PORT:-6380}
      REDIS_L1_DB: ${REDIS_L1_DB:-0}
      REDIS_L1_PASSWORD: ${REDIS_L1_PASSWORD:-scarerunner}
      HEARTBEAT_INTERVAL: ${HEARTBEAT_INTERVAL:-20}
      HEARTBEAT_TTL: ${HEARTBEAT_TTL:-60}

      # ── Python path (if using BaseService) ──────────────────────────────
      PYTHONPATH: /app/artifacts

    volumes:
      # Artifacts (for canonical.shared.services.base_service import)
      - ../../../../artifacts:/app/artifacts:ro

    ports:
      - "9001:5050"  # If service exposes HTTP (adjust as needed)

    restart: unless-stopped

    stop_grace_period: 30s

    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

    networks:
      - scareverse-net

networks:
  scareverse-net:
    external: true
```

---

### Step 4: Create requirements.txt

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

---

### Step 5: Create main.py (FastAPI Services) or entrypoint.sh (Native Services)

#### Option A: FastAPI Service (Backend, Ollama style)

```python
"""
My Service
"""

import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

import config

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

app = FastAPI(title="My Service", version="1.0.0")

# 🚨 MANDATORY: Register service availability in Redis L1
@app.on_event("startup")
async def startup():
    logger.info(f"🚀 Starting {config.WORKER_ID}...")
    
    from canonical.shared.services.base_service import BaseService
    import asyncio
    
    service = BaseService(config.WORKER_ID, service_port=config.WORKER_PORT, logger=logger)
    asyncio.create_task(service.heartbeat())  # Fire-and-forget
    logger.info(f"✅ {config.WORKER_ID} started with heartbeat (port_opened={config.WORKER_PORT})")

@app.get("/")
async def root():
    return {"status": "ok", "service": config.WORKER_ID}

@app.on_event("shutdown")
async def shutdown():
    logger.info(f"🛑 Shutting down {config.WORKER_ID}...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.WORKER_PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
```

#### Option B: Non-FastAPI Service (Traefik, Cloudflared style)

Create an **entrypoint.sh** script that:
1. Starts the native tool
2. Starts Python heartbeat in background or foreground
3. Handles graceful shutdown

**Example (Traefik-style, fire-and-forget heartbeat)**:
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
    echo "[entrypoint] Signal received - shutting down gracefully..."
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

**heartbeat.py** (Python script for non-FastAPI services):
```python
#!/usr/bin/env python3
"""
Service heartbeat registration (fire-and-forget).
Called by entrypoint.sh to register service availability in Redis L1.
"""

import asyncio
import logging
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("service-heartbeat")


def main() -> None:
    """Start heartbeat and keep it running."""
    # Ensure artifacts root is on the module path
    if "/app/artifacts" not in sys.path:
        sys.path.insert(0, "/app/artifacts")

    try:
        from canonical.shared.services.base_service import BaseService
    except ImportError as exc:
        logger.warning("BaseService unavailable: %s", exc)
        return

    service_name = os.getenv("WORKER_ID", "my-service")
    service_port = None
    if os.getenv("WORKER_PORT"):
        try:
            service_port = int(os.getenv("WORKER_PORT"))
        except ValueError:
            pass
    logger.info("Starting heartbeat for service: %s (port=%s)", service_name, service_port)

    async def _keep_alive() -> None:
        service = BaseService(service_name, service_port=service_port, logger=logger)
        await service.heartbeat()

    try:
        asyncio.run(_keep_alive())
    except Exception as exc:
        logger.error("Heartbeat failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

### Step 6: Create config.py (if needed)

**Optional for non-FastAPI services; required for FastAPI.**

```python
"""
Configuration for My Service
"""

import os

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ============================================================================
# Service Configuration
# ============================================================================

WORKER_ID = os.getenv("WORKER_ID", "my-service")
WORKER_PORT = int(os.getenv("WORKER_PORT", "5050"))

# ============================================================================
# Redis L1 (Heartbeat)
# ============================================================================

REDIS_L1_HOST = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_DB = int(os.getenv("REDIS_L1_DB", "0"))
REDIS_L1_PASSWORD = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))
HEARTBEAT_TTL = int(os.getenv("HEARTBEAT_TTL", "60"))
```

---

## 🚨 SERVICE HEARTBEAT REGISTRATION (MANDATORY)

**CRITICAL REQUIREMENT**: Every service worker MUST register availability in Redis L1 on startup.

### Heartbeat Patterns

**Option A: Fire-and-Forget** (FastAPI + uvicorn services)
- Heartbeat runs in background via `asyncio.create_task()`
- Does NOT block service startup
- Service starts immediately and accepts requests
- Heartbeat refreshes independently every HEARTBEAT_INTERVAL seconds
- **Example**: Backend, Ollama

```python
@app.on_event("startup")
async def startup():
    service = BaseService("my-service", service_port=5050, logger=logger)
    asyncio.create_task(service.heartbeat())  # Background
```

**Option B: Blocking Foreground** (Non-HTTP services like Cloudflared)
- Heartbeat runs as main foreground task (part of PID 1)
- Keeps container alive while heartbeat runs
- Used when native tool doesn't need HTTP server
- **Example**: Cloudflared waits in main loop with heartbeat

```bash
#!/bin/sh
cloudflared tunnel run &
python3 /app/heartbeat.py  # Blocking, keeps container alive
```

### BaseService Class (Provided by Framework)

**Location**: `canonical/shared/services/base_service.py`
**Method**: `await service.heartbeat()` - refreshes key + TTL in background loop
**Key**: `state:service:{service-name}:available`
**TTL**: Automatically = 3 × HEARTBEAT_INTERVAL (60s typical)

---

## Testing Service Workers

Create `tests/` directory with:

```python
# tests/conftest.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# tests/test_heartbeat.py
import pytest
from canonical.shared.services.base_service import BaseService

@pytest.mark.asyncio
async def test_heartbeat_registers_key(redis_client):
    service = BaseService("test-service", service_port=5050)
    await service.heartbeat()
    # Verify key exists in Redis
    key = "state:service:test-service:available"
    assert await redis_client.exists(key)
    
    # Verify JSON format: {"port_opened": true|false|null, "timestamp": float}
    import json
    value = await redis_client.get(key)
    data = json.loads(value)
    assert "port_opened" in data
    assert "timestamp" in data
    assert isinstance(data["timestamp"], float)
```

---

## 🚨 CRITICAL: manifest.json Dependencies

**The `dependencies` field is MANDATORY for services with external files (entrypoint.sh, heartbeat.py, etc.)**

When you update files that are **COPIED** in the Dockerfile (not just the Dockerfile itself), the Launcher needs to know to recalculate the checksum and rebuild the image.

### Why Dependencies Matter

**Without dependencies:**
- You update `heartbeat.py` 
- Dockerfile checksum stays the same (file content didn't change)
- Launcher sees same checksum → skips rebuild
- Old image continues running with OLD heartbeat.py
- **Result**: Service has broken heartbeat registration ❌

**With dependencies:**
- You update `heartbeat.py`
- Launcher checks if any dependency files changed
- Dependencies changed → triggers checksum recalculation
- New image is built with new heartbeat.py
- **Result**: Service runs with updated code ✅

### Implementation

**manifest.json:**
```json
{
  "version": "0.1",
  "name": "my-service",
  "build": true,
  "image": "localhost:5001/scareverse-my-service:staging",
  "dependencies": [
    "Dockerfile",
    "main.py",
    "config.py",
    "requirements.txt",
    "entrypoint.sh",
    "heartbeat.py"
  ],
  "generate_env_file": false,
  "totp_seed": false
}
```

**List all files that:**
1. Are COPIED in the Dockerfile
2. Would require a rebuild if changed
3. Affect the service behavior

**Common examples:**
- `Dockerfile` - Always include
- `main.py` - FastAPI app logic
- `entrypoint.sh` - Shell script for non-FastAPI services
- `heartbeat.py` - Service heartbeat registration
- `requirements.txt` - Python dependencies
- `config.py` - Configuration files
- Service-specific configs: `traefik.yml`, `nginx.conf`, etc.

### Real Example (Ollama Service)

```json
{
  "version": "0.1",
  "name": "ollama",
  "build": true,
  "image": "localhost:5001/scareverse-ollama:staging",
  "imageTag": "staging",
  "dependencies": [
    "Dockerfile.raw",
    "heartbeat.py",
    "entrypoint-raw.sh"
  ],
  "generate_env_file": false,
  "totp_seed": false
}
```

**Why these files?**
- `Dockerfile.raw` - If Dockerfile changes, rebuild needed
- `heartbeat.py` - If heartbeat registration logic changes, rebuild needed
- `entrypoint-raw.sh` - If startup sequence changes, rebuild needed

---

## File Structure

```
artifacts/canonical/services/my-service/
├── Dockerfile                  # REQUIRED: Service container image
├── docker-compose.yml          # REQUIRED: Standalone deployment
├── heartbeat.py                # REQUIRED: Redis L1 registration (if not FastAPI)
├── main.py                     # REQUIRED: FastAPI app or entrypoint logic
├── entrypoint.sh               # REQUIRED: For non-FastAPI services
├── config.py                   # OPTIONAL: Configuration (required for FastAPI)
├── requirements.txt            # REQUIRED (if Python-based)
├── manifest.json               # REQUIRED: Service metadata
├── README.md                   # REQUIRED: Setup & usage
└── tests/
    ├── conftest.py
    ├── test_heartbeat.py
    └── test_startup.py
```

---

## Checklist Before Submission

- [ ] Service located in `artifacts/canonical/services/{name}/`
- [ ] Dockerfile builds without errors
- [ ] docker-compose.yml uses external `scareverse-net`
- [ ] All config via environment variables (no hardcoding)
- [ ] BaseService heartbeat implemented (fire-and-forget or blocking)
- [ ] Graceful shutdown on SIGTERM/SIGINT
- [ ] Comprehensive logging (DEBUG, INFO, ERROR)
- [ ] Tests with >80% coverage
- [ ] README.md with setup + usage
- [ ] manifest.json with service metadata

---

**Document Version**: 1.0.0  
**Last Updated**: 2026-04-14
