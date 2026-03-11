---
processed: true
processed_date: 2026-03-09
themes:
  - workers
  - architecture
  - subprocess
modules:
  - shared
code_verified: true
dead_docs_found: false
---

# artifacts/canonical/shared/

Shared abstractions for `artifacts/canonical/` — reusable base classes, clients,
and utilities for both the GateKeeper service and subprocess job workers.

## Contents

| File | Purpose |
|------|---------|
| `base_worker.py` | Abstract base class (`BaseWorker`) for all subprocess job workers |
| `worker_executor.py` | `WorkerExecutor`: manages .venv lifecycle and subprocess dispatch |
| `redis_client.py` | Standalone async Redis L1 client (no backend imports) |
| `centralhub_client.py` | Standalone HTTP client for CentralHub service |
| `utils.py` | Shared utilities (ISO timestamps, job-type JSON loading, safe JSON parsing) |

## Usage

### BaseWorker

Every subprocess job worker must subclass `BaseWorker`:

```python
from canonical.shared.base_worker import BaseWorker

class MyWorker(BaseWorker):
    def execute(self) -> dict:
        return {"output": process(self.input_data)}

if __name__ == "__main__":
    worker = MyWorker.from_stdin()
    worker.run()  # reads stdin JSON, writes stdout JSON, exits 0/1
```

### WorkerExecutor

Used by GateKeeper to spawn worker subprocesses:

```python
from canonical.shared.worker_executor import WorkerExecutor

executor = WorkerExecutor(workers_path="/app/artifacts/canonical/workers")
result = await executor.execute(job_type, job_id, input_data, job_type_config)
```

## Import Path

When `PYTHONPATH=/app/artifacts` (Docker default):

```python
from canonical.shared import BaseWorker, WorkerExecutor
from canonical.shared.redis_client import get_redis_client
from canonical.shared.centralhub_client import get_centralhub_client
```

## Design Decisions

- **Self-contained**: No imports from `backend/`. Clients are standalone copies adapted for artifacts/ use.
- **Lazy singletons**: Redis and CentralHub clients use module-level singletons for connection reuse.
- **Path fallbacks**: All modules resolve paths for both Docker (absolute) and local development (relative).

---

## GateKeeper Service Registry

Each GateKeeper instance publishes its execution capability via a Redis heartbeat.
This enables smart job routing: jobs are enqueued to L1 only if the local GateKeeper
can actually execute them. Otherwise they fall back to L2 (CentralHub) for routing to
a capable GateKeeper on another host.

### Registry Key

```
state:gatekeeper:{worker_id}:serving_job_types = [
  "sd_generate",
  "ollama_generate",
  "rembg_removebackground"
]
```

This key is written by `GateKeeper._register_serving_capability()` every
`WORKER_HEARTBEAT_INTERVAL` seconds with TTL = `3 × WORKER_HEARTBEAT_INTERVAL`
(tolerates one missed heartbeat before expiry).

### Routing Decision in `create_job()`

```
1. Check service dependencies  → state:service:{name}:available
2. For "service" execution model:
   Check local GateKeeper capability → state:gatekeeper:{worker_id}:serving_job_types
3. Enqueue to L1 if both pass, L2 otherwise
4. Subprocess job-types bypass step 2 (always available locally)
```

### Example: Multi-Host Scenario

```
Host A (ScareRunner + SD container + GateKeeper):
  state:gatekeeper:gk-host-a:serving_job_types = ["sd_generate", "ollama_generate", "rembg_removebackground"]

Host B (ScareRunner + GateKeeper, NO SD container):
  state:gatekeeper:gk-host-b:serving_job_types = ["ollama_generate", "rembg_removebackground"]

create_job("sd_generate") called on Host B:
  → Check 1: stable-diffusion deps available? True (if sd is probed externally)
  → Check 2: gk-host-b can serve sd_generate? False (not in list)
  → Route to L2 automatically
  → GateKeeper on Host A picks it up from L2 and executes ✅
```

### Troubleshooting

| Symptom | Likely Cause | Resolution |
|---------|-------------|------------|
| Jobs always go to L2 | `state:gatekeeper:{id}:serving_job_types` key missing | GateKeeper not running or heartbeat failing |
| Service job-type never routes to L1 | Service health endpoint not responding | Check service container + health_path config |
| Key exists but wrong content | Stale TTL from previous GateKeeper instance | Wait for TTL expiry (3× HEARTBEAT_INTERVAL) or restart GateKeeper |
| Subprocess jobs still go to L2 | `execution_model` not set in job-type JSON | Add `"execution_model": "subprocess"` to job-type JSON |
