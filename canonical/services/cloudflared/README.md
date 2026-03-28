---
processed: true
processed_date: 2026-03-28
themes:
  - infrastructure
  - cloudflared
  - tunnel
modules:
  - infrastructure
code_verified: true
dead_docs_found: false
---
# Cloudflared Service Worker

Standalone service worker that runs a Cloudflare tunnel and exposes a FastAPI health sidecar for Launcher integration.

## Overview

| Property | Value |
|----------|-------|
| **Image** | `localhost:5001/scareverse-cloudflared:staging` |
| **Health port** | `8000` (internal, not published) |
| **Redis heartbeat key** | `state:service:cloudflared:available` |
| **Network** | `scareverse-net` (external) |

## Quick Start

```bash
# 1. Create Docker network (if not already created)
docker network create scareverse-net

# 2. Set your tunnel token
export TUNNEL_TOKEN=<token-from-cloudflare-dashboard>

# 3. Start the service
docker-compose up -d

# 4. Verify health
curl http://localhost:8000/health        # basic liveness
curl http://localhost:8000/health/detailed  # tunnel status

# 5. Check Redis heartbeat
redis-cli -h localhost -p 6380 -a scarerunner get state:service:cloudflared:available
```

## Configuration

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `TUNNEL_TOKEN` | _(empty)_ | **Required** for tunnel. Obtain from [Cloudflare dashboard](https://dash.cloudflare.com). |
| `TUNNEL_NAME` | `scareverse-tunnel` | Human-readable tunnel name. |
| `INGRESS_RULES` | `[]` | JSON array of ingress rule objects (see below). |
| `HEALTH_HOST` | `0.0.0.0` | Sidecar bind address. |
| `HEALTH_PORT` | `8000` | Sidecar port. |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `WORKER_ID` | `cloudflared` | Logical service name used for Redis heartbeat key. |
| `REDIS_L1_HOST` | `redis-local` | Redis L1 host. |
| `REDIS_L1_PORT` | `6380` | Redis L1 port. |
| `REDIS_L1_DB` | `0` | Redis L1 database index. |
| `REDIS_L1_PASSWORD` | `scarerunner` | Redis L1 password. |
| `HEARTBEAT_INTERVAL` | `20` | Seconds between heartbeat refreshes. |
| `HEARTBEAT_TTL` | `60` | Redis TTL for the heartbeat key (seconds). |

## Ingress Rules

Configure ingress rules as a JSON array in `INGRESS_RULES`:

```json
[
  {"hostname": "api.scareverse.cloud", "service": "http://centralhub:5051"},
  {"hostname": "cockpit.scareverse.cloud", "service": "http://vite-frontend:5173"},
  {"service": "http_status:404"}
]
```

## Token Setup

1. Log in to [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com).
2. Navigate to **Access → Tunnels → Create a tunnel**.
3. Copy the tunnel token shown during setup.
4. Store the token as a repository/environment secret (`TUNNEL_TOKEN`).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Basic liveness probe – 200 when sidecar is up. |
| `GET` | `/health/detailed` | Tunnel process status, config summary. |

### Example responses

```json
GET /health
{"status": "healthy"}

GET /health/detailed
{
  "status": "healthy",
  "tunnel": {
    "name": "scareverse-tunnel",
    "process_running": true,
    "token_configured": true,
    "ingress_rules_count": 3
  }
}
```

## Tests

```bash
cd artifacts/canonical/services/cloudflared
pip install -r requirements.txt pytest pytest-asyncio httpx
PYTHONPATH=../../../../artifacts pytest tests/ -v --tb=short
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Docker container: scareverse-cloudflared           │
│                                                     │
│  ┌──────────────────┐   ┌───────────────────────┐  │
│  │ cloudflared bin  │   │ FastAPI health sidecar │  │
│  │ (background)     │   │ :8000  (foreground)    │  │
│  └──────────────────┘   └───────────────────────┘  │
│          │                        │                 │
│    Cloudflare edge            Redis L1 heartbeat   │
│    (scareverse-net)          (state:service:        │
│                               cloudflared:available)│
└─────────────────────────────────────────────────────┘
```
