---
processed: true
processed_date: 2026-03-09
themes:
  - workers
  - subprocess
  - architecture
modules:
  - workers
code_verified: true
dead_docs_found: false
---

# artifacts/canonical/workers/

Subprocess job workers for ScareVerse — ephemeral Python processes spawned
by GateKeeper for job processing.

## Workers

| Directory | Job Types | Execution Model |
|-----------|-----------|-----------------|
| `rembg/` | `rembg_removebackground`, `REMOTE_REMBG`, `background_removal` | subprocess |
| `ollama-wrapper/` | `ollama_generate`, `ollama_chat` | subprocess (HTTP wrapper) |
| `stable-diffusion-wrapper/` | `sd_generate` | subprocess (HTTP wrapper) |

## Communication Contract

Each worker communicates with GateKeeper via stdin/stdout JSON:

```
GateKeeper → stdin:  {"job_id": "...", "job_type": "...", "input_data": {...}}
Worker     → stdout: {"success": true,  "result": {...}}
                     {"success": false, "error": "..."}
```

Logs go to stderr and are captured/logged by GateKeeper.

## Adding a New Worker

1. Create `workers/{name}/` directory
2. Implement `worker.py` extending `BaseWorker`:
   ```python
   from canonical.shared.base_worker import BaseWorker

   class MyWorker(BaseWorker):
       def execute(self) -> dict:
           return {"output": process(self.input_data)}
   ```
3. Create `main.py` as entry point:
   ```python
   #!/usr/bin/env python3
   import json, sys
   from worker import MyWorker

   if __name__ == "__main__":
       data = json.loads(sys.stdin.read())
       worker = MyWorker(data["job_id"], data["job_type"], data["input_data"])
       worker.run()
   ```
4. Create `requirements.txt` with dependencies
5. Add job-type JSON to `job-types/{name}.json` with `execution_model: "subprocess"`

GateKeeper auto-creates `.venv/` on first execution and installs `requirements.txt`.

## Isolated Dependencies

Each worker has its own `.venv/` managed by GateKeeper's `WorkerExecutor`:

```
workers/
├── rembg/
│   ├── .venv/          ← auto-created by GateKeeper on first run
│   ├── main.py
│   ├── worker.py
│   └── requirements.txt
└── ollama-wrapper/
    ├── .venv/
    ├── main.py
    ├── worker.py
    └── requirements.txt
```

This provides **dependency isolation**: rembg can use PIL v10 while another worker
uses PIL v9 without conflicts.
