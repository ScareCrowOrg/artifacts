---
processed: true
processed_date: 2026-03-11
themes:
  - infrastructure
  - vite
  - frontend
  - docker
  - service-worker
modules:
  - services
code_verified: true
dead_docs_found: false
---

# Vite Service

Standalone Docker service for the Vite dev server.

Compiles TypeScript/Vue components on-demand for dynamic cell and book types.  
Previously managed by supervisord inside the unified `infrastructure/scarerunner/` container.  
Now an isolated service worker following the `ADDING_NEW_WORKER.md` pattern.

---

## Architecture

```
artifacts/canonical/services/vite/
├── Dockerfile          Node 20-alpine, runs npm run dev
├── docker-compose.yml  Standalone compose (external: scareverse-net)
└── README.md           This file
```

**Port**: `5052` (Vite dev server)  
**Health check**: `GET http://localhost:5052/` (any HTTP response = alive)

---

## Usage

```bash
# From project root

# Build
docker-compose -f artifacts/canonical/services/vite/docker-compose.yml build

# Start
docker-compose -f artifacts/canonical/services/vite/docker-compose.yml up -d

# Logs (with HMR updates and viewer warmup output)
docker-compose -f artifacts/canonical/services/vite/docker-compose.yml logs -f

# Stop
docker-compose -f artifacts/canonical/services/vite/docker-compose.yml down
```

> **Prerequisite**: `scareverse-net` Docker network must exist.  
> Created automatically by the meta-orchestrator or the Redis service.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ENV` | `development` | Node environment |
| `VITE_HMR_HOST` | `localhost` | HMR WebSocket host |
| `VITE_HMR_PORT` | `5052` | HMR WebSocket port |
| `VITE_HMR_PROTOCOL` | `ws` | HMR protocol (`ws` or `wss`) |
| `VITE_CORS_ORIGINS` | `http://localhost:8000,...` | Allowed CORS origins |
| `VITE_TRACE` | `false` | Enable performance tracing |
| `VITE_TRACE_RESOLVE` | `false` | Trace module resolution |
| `VITE_TRACE_LOAD` | `false` | Trace module load times |
| `VITE_DEBUG` | `false` | Enable Vite debug output |

---

## Volume Mounts

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `./artifacts/canonical` | `/app/artifacts/canonical` | `rw` | Cell/book types to compile |
| `./artifacts/runtime` | `/app/artifacts/runtime` | `rw` | Runtime artifacts |
| `./artifacts/sandbox` | `/app/artifacts/sandbox` | `rw` | Sandbox artifacts |
| `./artifacts/shared` | `/app/artifacts/shared` | `rw` | Shared utilities (Vue components, stores, etc.) |
| `./artifacts/package.json` | `/app/artifacts/package.json` | `ro` | Node.js manifest |
| `./artifacts/vite.config.ts` | `/app/artifacts/vite.config.ts` | `ro` | Vite configuration |

> `node_modules` is **not** mounted — installed inside the container at build time  
> to ensure Linux-native binaries work correctly.

---

## Features

- **On-demand compilation**: TypeScript/Vue files compiled when first requested
- **HMR**: File changes trigger instant browser updates
- **Viewer warmup**: Pre-compiles all viewers on startup (see `vite.config.ts`)
- **Rebuild observability**: Logs file change events and HMR triggers
- **Performance tracing**: Optional detailed timing via `VITE_TRACE=true`

---

## Health Check

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5052/
# Any 2xx or 4xx response = server is running
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
