---
processed: true
processed_date: 2026-03-28
themes:
  - job-types
  - gatekeeper
  - workers
modules:
  - backend
  - infrastructure
code_verified: true
dead_docs_found: false
---
# Job Type Definitions

This directory contains canonical job-type definitions for the ScareVerse job queue system.

## Overview

Each JSON file defines a job type with its routing configuration, storage strategy, and availability signaling.

## Job Types

| File | Job Type | Worker | Queue |
|------|----------|--------|-------|
| `ollama_generate.json` | `ollama_generate` | ollama | `scareverse:cpu-jobs:queue` |
| `ollama_chat.json` | `ollama_chat` | ollama | `scareverse:cpu-jobs:queue` |
| `sd_generate.json` | `sd_generate` | stable-diffusion | `scareverse:cpu-jobs:queue` |
| `rembg_removebackground.json` | `rembg_removebackground` | rembg | `scareverse:cpu-jobs:queue` |
| `instantmesh.json` | `instantmesh` | instantmesh | `scareverse:3d-jobs:queue` |

## Schema

Each job-type JSON file contains:

```json
{
  "job_type": "canonical_name",
  "description": "Human-readable description",
  "worker": "worker service name",
  "queue": "Redis queue name (L1)",
  "result_storage": "rpush_l1 | hset_l2",
  "result_key_prefix": "Redis key prefix for results",
  "result_key_ttl": 120,
  "timeout": 60,
  "worker_availability_key": "state:worker:{job_type}:available",
  "aliases": ["alias1", "alias2"]
}
```

## Queue Architecture

The system uses 2 consolidated queues:

- `scareverse:cpu-jobs:queue` — CPU/GPU jobs: ollama, rembg, stable-diffusion
- `scareverse:3d-jobs:queue` — 3D mesh jobs: instantmesh

GateKeeper monitors both queues with owner-first scheduling (L1 first, then L2).

## Worker Availability

Each worker registers availability in Redis L1:
- **Key:** `state:worker:{job_type}:available`
- **Value:** `{"worker_id": "...", "capacity": 5, "timestamp": "..."}`
- **TTL:** 30-60 seconds (refreshed while worker is running)

The `redis_job_client` checks this key before enqueuing to decide whether to push to L1 (fast local) or fallback to CentralHub L2 (global).
