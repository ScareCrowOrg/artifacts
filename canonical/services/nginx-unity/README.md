---
processed: true
processed_date: 2026-03-28
themes:
  - infrastructure
  - nginx
modules:
  - infrastructure
code_verified: true
dead_docs_found: false
---
# Nginx Unity Service Worker

Unified Nginx reverse proxy with a FastAPI health sidecar for Launcher integration.

## Overview

| Property | Value |
|----------|-------|
| **Image** | `localhost:5001/scareverse-nginx-unity:staging` |
| **Nginx port** | `80` (configurable via `NGINX_PORT`) |
| **Sidecar port** | `9000` (internal; configurable via `SIDECAR_PORT`) |
| **Redis heartbeat key** | `state:service:nginx-unity:available` |
| **Network** | `scareverse-net` (external) |

## Quick Start

```bash
# 1. Create Docker network (if not already created)
docker network create scareverse-net

# 2. Start the service
docker-compose up -d

# 3. Verify Nginx is routing
curl http://localhost:8080/health     # Nginx health endpoint → "OK"

# 4. Verify sidecar health endpoints (internal, use exec or adjust ports)
docker exec scareverse-nginx-unity curl http://localhost:9000/health
docker exec scareverse-nginx-unity curl http://localhost:9000/health/detailed

# 5. Check Redis heartbeat
redis-cli -h localhost -p 6380 -a scarerunner get state:service:nginx-unity:available
```

## Configuration

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `NGINX_PORT` | `80` | HTTP port Nginx listens on inside the container. |
| `NGINX_EXTERNAL_PORT` | `8080` | Host port mapped to `NGINX_PORT` (docker-compose only). |
| `LOG_LEVEL` | `warn` | Nginx error log level: `debug`, `info`, `warn`, `error`. |
| `CENTRALHUB_UPSTREAM` | `centralhub:5051` | CentralHub API upstream (`host:port`). |
| `FRONTEND_UPSTREAM` | `vite-frontend:5173` | Vite frontend upstream (`host:port`). |
| `SCARERUNNER_UPSTREAM` | `scarerunner:5050` | ScareRunner upstream (`host:port`). |
| `GATEKEEPER_UPSTREAM` | `gatekeeper:8000` | GateKeeper upstream (`host:port`). |
| `SIDECAR_HOST` | `0.0.0.0` | FastAPI sidecar bind address. |
| `SIDECAR_PORT` | `9000` | FastAPI sidecar port. |
| `WORKER_ID` | `nginx-unity` | Logical service name for Redis heartbeat key. |
| `REDIS_L1_HOST` | `redis-local` | Redis L1 host. |
| `REDIS_L1_PORT` | `6380` | Redis L1 port. |
| `REDIS_L1_DB` | `0` | Redis L1 database index. |
| `REDIS_L1_PASSWORD` | `scarerunner` | Redis L1 password. |
| `HEARTBEAT_INTERVAL` | `20` | Seconds between heartbeat refreshes. |
| `HEARTBEAT_TTL` | `60` | Redis TTL for the heartbeat key (seconds). |
| `UPSTREAM_CHECK_TIMEOUT` | `3` | Seconds to wait when probing upstreams in `/health/detailed`. |

## Routing Table

| Location | Upstream | Notes |
|----------|----------|-------|
| `/api/*` | `centralhub` | Forwards `Authorization` header; 300 s timeout. |
| `/gatekeeper/*` | `gatekeeper` | Job dispatcher. |
| `/runner/*` | `scarerunner` | Internal only. |
| `/health` | _(Nginx)_ | Returns `"OK"` (plain text) for Docker health checks. |
| `/` | `frontend` | Catch-all → Vite dev server. |

## Sidecar Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Basic liveness – 200 when sidecar is running. |
| `GET` | `/health/detailed` | Upstream availability probe. |

### Example response – `/health/detailed`

```json
{
  "status": "healthy",
  "upstreams": {
    "centralhub": "up",
    "frontend": "up",
    "scarerunner": "down",
    "gatekeeper": "up"
  }
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Docker container: scareverse-nginx-unity               │
│                                                         │
│  ┌──────────────────────────┐  ┌─────────────────────┐ │
│  │  Nginx reverse proxy     │  │  FastAPI sidecar    │ │
│  │  :80 (foreground via     │  │  :9000 (foreground) │ │
│  │   entrypoint.sh)         │  │                     │ │
│  │                          │  │  /health            │ │
│  │  /api/   → centralhub    │  │  /health/detailed   │ │
│  │  /runner/→ scarerunner   │  │                     │ │
│  │  /       → frontend      │  │  Redis L1 heartbeat │ │
│  │  /health → "OK"          │  │  (nginx-unity key)  │ │
│  └──────────────────────────┘  └─────────────────────┘ │
│              │                           │              │
│         scareverse-net               Redis L1           │
└─────────────────────────────────────────────────────────┘
```

## Tests

```bash
cd artifacts/canonical/services/nginx-unity
pip install -r requirements.txt pytest pytest-asyncio httpx
PYTHONPATH=../../../../artifacts pytest tests/ -v --tb=short
```
