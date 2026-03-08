# GateKeeper Worker

Central job dispatcher for the ScareVerse multi-source queue system.

## Overview

GateKeeper pulls jobs from dual Redis sources (L1 owner + L2 global) using
owner-first scheduling and routes them to atomic workers via HTTP POST.

## Dynamic Worker Discovery

Job types and their worker endpoints are loaded at startup from
`artifacts/canonical/job-types/*.json`. **No code change is required to add a
new worker** — simply add a JSON file and restart GateKeeper.

### Job-Type JSON Schema

Each file in `artifacts/canonical/job-types/` must include:

```json
{
  "name": "my_worker_op",
  "worker_type": "my-worker",
  "endpoint": "http://scareverse-my-worker:9000",
  "queue_l1": "scareverse:cpu-jobs:queue",
  "queue_l2": "scareverse:cpu-jobs:queue",
  "result_storage": "rpush_l1",
  "result_key_prefix": "scareverse:my-worker-results",
  "result_key_ttl": 120,
  "timeout": 60,
  "aliases": ["my_worker_op", "legacy_alias"]
}
```

| Field | Description |
|-------|-------------|
| `name` | Primary job-type key (must match filename without `.json`) |
| `worker_type` | Worker service name (used as `worker_name` in routing) |
| `endpoint` | Default HTTP base URL of the atomic worker |
| `queue_l1` | Redis L1 queue name |
| `queue_l2` | Redis L2 queue name |
| `result_storage` | `rpush_l1` (result RPUSH to L1) or `hset_l2` (HSET to L2) |
| `result_key_prefix` | Redis key prefix for storing results |
| `result_key_ttl` | TTL in seconds for result keys |
| `timeout` | HTTP request timeout in seconds |
| `aliases` | Legacy or alternate names that map to this job type |

### Worker Endpoint Configuration

Endpoints default to the values in each JSON file. They can be overridden per
deployment via environment variables:

```
WORKER_{JOB_TYPE_UPPER}_ENDPOINT=http://custom-host:port
```

Examples:
```bash
WORKER_OLLAMA_GENERATE_ENDPOINT=http://custom-ollama:9000
WORKER_OLLAMA_CHAT_ENDPOINT=http://custom-ollama:9000
WORKER_SD_GENERATE_ENDPOINT=http://custom-sd:9000
WORKER_REMBG_REMOVEBACKGROUND_ENDPOINT=http://custom-rembg:9000
WORKER_INSTANTMESH_ENDPOINT=http://custom-instantmesh:8000
```

The env var name is derived from the job-type `name` field:
`WORKER_` + `name.upper().replace('-', '_')` + `_ENDPOINT`

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_L1_HOST` | `redis-local` | L1 Redis host (ScareRunner) |
| `REDIS_L1_PORT` | `6380` | L1 Redis port |
| `REDIS_L1_PASSWORD` | `scarerunner` | L1 Redis password |
| `REDIS_L2_HOST` | `host.docker.internal` | L2 Redis host (CentralHub) |
| `REDIS_L2_PORT` | `6379` | L2 Redis port |
| `BRPOP_L1_TIMEOUT` | `1` | Owner queue poll timeout (seconds) |
| `BRPOP_L2_TIMEOUT` | `20` | Global queue block timeout (seconds) |
| `WORKER_MAX_RETRIES` | `3` | Max HTTP retries per job |
| `WORKER_RETRY_DELAY` | `2.0` | Base retry delay (seconds, exponential back-off) |
| `LOG_LEVEL` | `INFO` | Logging level |

## Running

```bash
# Local (requires Redis running)
python main.py

# Docker
docker-compose up gatekeeper
```

## Tests

```bash
# From this directory
python3 -m pytest tests/ -v
```

## Adding a New Worker

1. Create `artifacts/canonical/job-types/<job_type>.json` with all required fields.
2. Restart GateKeeper — it will auto-discover and start routing the new job type.
3. Verify startup logs show `Loaded job-type: <job_type>`.
