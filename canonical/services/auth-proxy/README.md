# Auth Proxy (Recepção)

Lightweight Rust microservice that intercepts `/artifacts/*` requests, validates the `sessionId` cookie via Backend's `/api/v1/auth/session-check`, and proxies validated requests transparently to Vite.

## Overview

```
Nginx Unit (/artifacts/* → auth-proxy:5055)
    ↓
Auth Proxy (Recepção)
    ├─ Extract Cookie: sessionId
    ├─ POST /api/v1/auth/session-check?uri=/artifacts/...  →  Backend
    │       200 OK   → proxy to Vite (stream response)
    │       403      → return 403 immediately
    │       other    → return 500
    └─ Vite serves artifact → Auth Proxy streams back to client
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PROXY_PORT` | `5055` | Port the proxy listens on |
| `VITE_UPSTREAM` | `http://vite:5052` | Vite upstream base URL |
| `BACKEND_AUTH_URL` | `http://backend:5050/api/v1/auth/session-check` | Backend session-check endpoint |
| `REDIS_L1_HOST` | `redis-local` | Redis L1 host for heartbeat |
| `REDIS_L1_PORT` | `6380` | Redis L1 port |
| `REDIS_L1_PASSWORD` | `scarerunner` | Redis L1 password |
| `REDIS_L1_DB` | `0` | Redis L1 database index |
| `HEARTBEAT_INTERVAL` | `20` | Heartbeat refresh interval (seconds) |
| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARN, ERROR |

## HTTP Endpoints

| Method | Path | Description |
|---|---|---|
| `*` | `/artifacts/*` | Auth-validated proxy to Vite |
| `GET` | `/health` | Health check (returns `200 OK`) |

## Redis Keys

| Key | TTL | Description |
|---|---|---|
| `state:service:auth-proxy:available` | `HEARTBEAT_INTERVAL * 3` | Readiness signal for NginxUnitRouter. TTL is 3× the interval so the key survives up to 2 missed heartbeats before expiring. |

## Deployment

### Build and run (standalone)

```bash
# From repository root
docker-compose -f artifacts/canonical/services/auth-proxy/docker-compose.yml up --build
```

### Run via meta-orchestrator

```bash
docker-compose -f artifacts/canonical/services/docker-compose.yml up
```

### Manual build

```bash
cd artifacts/canonical/services/auth-proxy
cargo build --release
./target/release/auth-proxy
```

## Testing

```bash
# Health check
curl http://localhost:5055/health

# Test with valid session (should proxy to Vite)
curl -H "Cookie: sessionId=<valid-token>" http://localhost:5055/artifacts/canonical/cell_types/...

# Test without session (should return 403)
curl http://localhost:5055/artifacts/canonical/cell_types/...
```

## Security

- Missing `sessionId` → 403 Forbidden
- Invalid / expired `sessionId` → 403 Forbidden (Backend enforces TTL via Redis)
- RBAC violations → 403 Forbidden (Backend enforces owner-only, forbidden extensions)
- Backend unavailable → 500 Internal Server Error (fail-secure)

## Architecture Notes

- **Host header rewriting**: Incoming requests carry the public FQDN as `Host` (e.g. `scare.scareverse.net`). Auth Proxy rewrites it to `vite:5052` before forwarding so Vite processes the request correctly.
- **Connection pooling**: `reqwest` client is shared across requests with `pool_max_idle_per_host = 20`.
- **Streaming**: Vite responses are streamed directly to the client without buffering.
- **Graceful shutdown**: SIGTERM/SIGINT handler waits for in-flight requests to complete (up to 30s).
