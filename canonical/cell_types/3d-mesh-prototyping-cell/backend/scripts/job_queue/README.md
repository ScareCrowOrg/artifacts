# Job Queue Module

Redis-based job queueing and status tracking for 3D mesh generation with hybrid Windows Worker integration.

## Overview

This module provides the infrastructure for asynchronous 3D mesh generation by queueing jobs to Redis and coordinating with a Windows Worker that performs GPU-accelerated processing.

## Architecture

```
┌─────────────┐      ┌─────────────┐      ┌──────────────┐
│   Backend   │─────▶│    Redis    │◀─────│   Windows    │
│ (Kind/Linux)│      │  Job Queue  │      │    Worker    │
└─────────────┘      └─────────────┘      └──────────────┘
       │                                           │
       └──────────── Shared Volume ───────────────┘
```

## Modules

### redis_client.py
Manages Redis client initialization and connection pooling.

**Functions:**
- `get_redis_client()`: Returns async Redis client for job queueing

**Connection Strategy:**
1. Attempts to import from core backend app (`app.core.redis_client`)
2. Falls back to standalone Redis client for direct script execution
3. Uses `REDIS_URL` environment variable (default: `redis://localhost:6379/0`)

### file_manager.py
Manages shared volume path configuration for file transfer between Backend and Worker.

**Functions:**
- `get_shared_volume_path()`: Returns Path object for shared volume

**Path Mapping (MVP 4.1):**
- Backend writes to: `/app/.local-dev-data/scareverse-data/jobs/{id}/input.png`
- Windows sees: `<PROJECT_ROOT>\.local-dev-data\scareverse-data\jobs\{id}\input.png`
- Worker reads from: `/data/jobs/{id}/input.png` (volume mount)

**Environment Variables:**
- `SHARED_VOLUME_PATH`: Override default shared volume path (default: `/app/.local-dev-data/scareverse-data`)

### queue_manager.py
Implements job queueing, status tracking, and result retrieval.

**Functions:**

#### `queue_3d_generation_job(input_image, target_faces, enable_draco, compression_level, target_size_mb)`
Queue a 3D generation job to Redis for Windows Worker processing.

**Process:**
1. Generate unique `job_id`
2. Write input image to shared volume
3. Store job metadata in Redis Hash
4. Push job to Redis queue
5. Return `job_id` for client polling

**Redis Keys:**
- Status: `scareverse:3d-status:{job_id}` (Hash)
- Queue: `scareverse:3d-jobs:queue` (List)

**Returns:**
```python
{
    "success": bool,
    "job_id": str,
    "message": str,
    "error": str  # if failed
}
```

#### `get_job_status(job_id)`
Retrieve job status and results from Redis.

**Process:**
1. Read job status from Redis Hash
2. If completed, read GLB file from shared volume
3. Parse metadata and optimization flags
4. Return mesh data and metadata

**Status Values:**
- `queued`: Job in queue, not yet picked up
- `processing`: Worker is processing the job
- `completed`: Job completed, mesh available
- `failed`: Job failed, error message available
- `not_found`: Job ID not found in Redis
- `error`: System error during status retrieval

**Returns (completed):**
```python
{
    "status": "completed",
    "mesh_data": str,  # Base64-encoded GLB
    "metadata": dict,  # Processing metadata
    "blender_optimized": bool,
    "blender_error": str,
    "sf3d_completed": bool,
    "message": str
}
```

**Returns (failed):**
```python
{
    "status": "failed",
    "error": str
}
```

**Returns (in progress):**
```python
{
    "status": "queued" | "processing"
}
```

## Usage Example

```python
from job_queue import queue_3d_generation_job, get_job_status

# Queue a job
result = await queue_3d_generation_job(
    input_image="data:image/png;base64,...",
    target_faces=50000,
    enable_draco=True,
    compression_level=7,
    target_size_mb=5.0
)

job_id = result["job_id"]

# Poll for status
status = await get_job_status(job_id)

if status["status"] == "completed":
    mesh_data = status["mesh_data"]
    metadata = status["metadata"]
elif status["status"] == "failed":
    error = status["error"]
```

## Error Handling

### File Write Errors
- Invalid base64 image data
- Shared volume not accessible
- Insufficient disk space
- File size mismatch after write

### Redis Errors
- Connection failures (retries via redis-py)
- WRONGTYPE error (key exists with wrong data type)
- Key expiration (jobs expire after 1 hour)

### File Read Errors (Results)
- Output file not found (volume sync delay)
- File size mismatch
- Corrupted GLB data

**Retry Strategy:**
- File read retries with filesystem cache invalidation (5 attempts, 1s delay)
- Directory listing forces cache refresh
- Extensive diagnostic logging for troubleshooting

## Testing

**Unit Tests:**
```bash
pytest tests/unit/test_queue_manager.py
pytest tests/unit/test_redis_client.py
pytest tests/unit/test_file_manager.py
```

**Persistence Tests (mongomock):**
```bash
pytest tests/persistence/test_job_queue.py
```

## Monitoring

**Redis Inspection:**
```bash
# List all queued jobs
redis-cli LRANGE scareverse:3d-jobs:queue 0 -1

# Get job status
redis-cli HGETALL scareverse:3d-status:{job_id}

# List all status keys
redis-cli KEYS "scareverse:3d-status:*"
```

**Shared Volume Inspection:**
```bash
# List job directories
ls -la /app/.local-dev-data/scareverse-data/jobs/

# Inspect specific job
ls -la /app/.local-dev-data/scareverse-data/jobs/{job_id}/
```

## Future Enhancements

- [ ] Dead letter queue for failed jobs
- [ ] Job prioritization (priority queue)
- [ ] Job cancellation API
- [ ] Batch job submission
- [ ] Job result caching (completed jobs)
- [ ] Prometheus metrics export
- [ ] Distributed tracing (OpenTelemetry)

## References

- [Redis Queue Pattern](https://redis.io/docs/manual/patterns/reliable-queue/)
- [Shared Volume Architecture](../../docs/SHARED_VOLUME_ARCHITECTURE.md)
- [Windows Worker Integration](../../docs/WINDOWS_WORKER_INTEGRATION.md)

---

**Last Updated:** 2026-01-28 (Phase 6 - Hybrid Generation Modes)  
**Module Version:** 2.0.0  
**Maintained By:** Backend Agent
