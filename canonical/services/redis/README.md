---
processed: true
processed_date: 2026-03-11
themes:
  - infrastructure
  - redis
  - cache
  - docker
  - service-worker
modules:
  - services
code_verified: true
dead_docs_found: false
---

# Redis Service (L1)

Local Redis cache (L1) for ScareVerse artifact metadata and session data.

Previously defined inline in `docker-compose.scarerunner.yml`.  
Now an isolated service worker for independent lifecycle management.

---

## Architecture

```
artifacts/canonical/services/redis/
├── docker-compose.yml  redis:7-alpine with AOF persistence
└── README.md           This file
```

**Port**: `6380` (avoids conflict with Kind cluster Redis on 6379)  
**Health check**: `redis-cli -p 6380 -a <password> ping`

---

## Usage

```bash
# From project root

# Start
docker-compose -f artifacts/canonical/services/redis/docker-compose.yml up -d

# Logs
docker-compose -f artifacts/canonical/services/redis/docker-compose.yml logs -f

# Stop
docker-compose -f artifacts/canonical/services/redis/docker-compose.yml down

# Stop and remove volumes (clears all cached data)
docker-compose -f artifacts/canonical/services/redis/docker-compose.yml down -v
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_L1_PASSWORD` | `scarerunner` | Redis password |

---

## Ports

| Port | Purpose |
|------|---------|
| `6380` | Redis L1 (local cache) |

Port `6380` is used intentionally (not default `6379`) to avoid conflicts with the Kind cluster Redis (`host.docker.internal:6379`).

---

## Persistence

Data is stored in a named Docker volume (`scareverse_redis_local_data`) with AOF (Append-Only File) persistence enabled. Data survives container restarts.

To clear all cached data:
```bash
docker-compose -f artifacts/canonical/services/redis/docker-compose.yml down -v
```

---

## Network

This service **creates** the `scareverse-net` bridge network (other services use `external: true`).  
Always start Redis first, or use the meta-orchestrator which handles ordering automatically.

---

## Startup Order

```
redis-local (6380) → backend (5050) → vite (5052)
```

Use the meta-orchestrator to start all services with correct ordering:

```bash
docker-compose -f artifacts/canonical/services/docker-compose.yml up
```
