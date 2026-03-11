---
processed: true
processed_date: 2026-03-11
themes:
  - infrastructure
  - backend
  - docker
  - service-worker
modules:
  - services
code_verified: true
dead_docs_found: false
---

# Backend Service

Standalone Docker service for the ScareVerse Backend API (FastAPI + uvicorn).

Previously managed by supervisord inside the unified `infrastructure/scarerunner/` container.  
Now an isolated service worker following the `ADDING_NEW_WORKER.md` pattern.

---

## Architecture

```
artifacts/canonical/services/backend/
├── Dockerfile          Python 3.11-slim + Node.js 20 + gemini-cli
├── docker-compose.yml  Standalone compose (external: scareverse-net)
├── entrypoint.sh       Handles UVICORN_RELOAD toggle
└── README.md           This file
```

**Port**: `5050` (Backend API)  
**Health check**: `GET http://localhost:5050/api/health`

**Gemini CLI is installed in this container** (not moved to Vite service) because:
- Backend uses shared classes from `artifacts/shared/`
- Gemini CLI reads and writes files in `artifacts/`

---

## Usage

```bash
# From project root

# Build
docker-compose -f artifacts/canonical/services/backend/docker-compose.yml build

# Start
docker-compose -f artifacts/canonical/services/backend/docker-compose.yml up -d

# Logs
docker-compose -f artifacts/canonical/services/backend/docker-compose.yml logs -f

# Stop
docker-compose -f artifacts/canonical/services/backend/docker-compose.yml down
```

> **Prerequisite**: Redis must be running first.  
> Start via `artifacts/canonical/services/redis/docker-compose.yml` or the meta-orchestrator.

---

## Configuration

All parameters are passed via environment variables. Copy `.env.example` (project root) to `.env` and adjust.

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Listen address |
| `API_PORT` | `5050` | Listen port |
| `API_DEBUG` | `true` | Enable debug mode |
| `UVICORN_RELOAD` | `false` | Enable hot reload (`true` for development) |
| `AUTH_ENABLED` | `true` | Enable authentication |
| `AUTH_TOKEN` | — | API auth token |
| `SECRET_KEY` | — | Session secret key |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `REDIS_L1_HOST` | `redis-local` | Redis L1 hostname (Docker DNS) |
| `REDIS_L1_PORT` | `6380` | Redis L1 port |
| `REDIS_L1_PASSWORD` | `scarerunner` | Redis L1 password |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Default Gemini model |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `BASE_DIR` | `/app` | Application base directory |
| `ARTIFACTS_DIR` | `artifacts` | Artifacts subdirectory name |

---

## Volume Mounts

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `./artifacts/canonical` | `/app/artifacts/canonical` | `rw` | Immutable cell/book types (Gemini CLI writes here) |
| `./artifacts/runtime` | `/app/artifacts/runtime` | `rw` | Dynamic runtime state |
| `./artifacts/sandbox` | `/app/artifacts/sandbox` | `rw` | Isolated sandbox |
| `./artifacts/shared` | `/app/artifacts/shared` | `rw` | Shared utilities (single source of truth) |
| `./artifacts/package.json` | `/app/artifacts/package.json` | `ro` | Node.js manifest |
| `./artifacts/vite.config.ts` | `/app/artifacts/vite.config.ts` | `ro` | Vite config reference |
| `./backend` | `/app/backend` | `ro` | Backend application code |
| `./backend/logs` | `/app/backend/logs` | `rw` | Audit logs (writable) |

> `node_modules` is **not** mounted — built inside the container at image build time  
> to ensure Linux-native binaries (rollup, vite, etc.).

---

## Health Check

```bash
curl http://localhost:5050/api/health
# Expected: HTTP 200
```

---

## Startup Order

```
redis-local (6380) → backend (5050) → vite (5052)
```

Use the meta-orchestrator to start all services with correct ordering:

```bash
docker-compose -f artifacts/canonical/services/docker-compose.yml up
```
