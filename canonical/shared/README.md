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
