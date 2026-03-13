---
processed: true
processed_date: 2025-12-08
themes:
  - api
  - backend
  - issues-management
  - rest-api
  - orchestration
modules:
  - backend
  - api
code_verified: true
dead_docs_found: false
---
# Issues Router - Backend Endpoints for IssuesDashboard

## Overview

This module implements the REST API endpoints requested in the issue for managing the issues ingestion queue. The endpoints provide control over ingestion, processing, and monitoring of cells in the issues book.

## Endpoints

All endpoints are accessible at `/api/issues/*`:

### 1. Manual Ingestion
**POST `/api/issues/ingest`**

Triggers the `ingest.py` script to discover and create ingestion cells.

**Request Body:**
```json
{
  "source_dir": "/path/to/documents",  // Optional
  "dry_run": false                      // Optional
}
```

**Response:**
```json
{
  "status": "ok",
  "ingested": 0,
  "message": "Ingest process started (PID: 12345)"
}
```

### 2. Manual Processing
**POST `/api/issues/process`**

Immediately processes all pending cells in the issues queue, bypassing the regular polling interval.

**Response:**
```json
{
  "status": "ok",
  "processed": 3
}
```

### 3. Start Monitoring
**POST `/api/issues/monitoring/start`**

Starts the automatic monitoring loop that continuously processes pending cells at configured intervals.

**Response:**
```json
{
  "status": "monitoring_started"
}
```

### 4. Stop Monitoring
**POST `/api/issues/monitoring/stop`**

Stops the automatic monitoring loop, halting automatic processing.

**Response:**
```json
{
  "status": "monitoring_stopped"
}
```

### 5. Pause Processing
**POST `/api/issues/processing/pause`**

Pauses the processing of cells while keeping the monitoring loop active. Cells will not be processed until resumed.

**Response:**
```json
{
  "status": "processing_paused"
}
```

### 6. Resume Processing
**POST `/api/issues/processing/resume`**

Resumes the processing of cells after being paused.

**Response:**
```json
{
  "status": "processing_resumed"
}
```

## Architecture

The router integrates with the existing orchestrator (`orchestrator.py`) which provides the core functionality:

- **Orchestrator**: Manages cell workflow execution, state transitions, and monitoring
- **Issues Router**: Provides REST API interface for orchestrator control
- **Issues Dashboard Router**: Provides extended functionality and SSE for real-time updates

## State Management

Cell states are managed through the orchestrator:
- `PENDENTE` → `EXECUTANDO` → `FINALIZADO` or `ERRO`

The orchestrator ensures:
- Lock/mutual exclusion during cell processing
- Configurable polling intervals and concurrency limits
- Manual trigger support via `force_process_pending_issues()`

## Integration

The router is registered in `main.py`:

```python
from .issues_router import issues_router
app.include_router(issues_router, prefix=API_PREFIX)
```

This makes all endpoints available at `/api/issues/*`.

## Testing

Comprehensive tests are available in:
- `tests/endpoints/backend/test_issues_router.py`

Tests cover:
- Successful operations
- Error handling
- Missing orchestrator scenarios
- Workflow integration

## Usage Example

```javascript
// Trigger manual ingestion
await fetch('/api/issues/ingest', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    source_dir: '/path/to/docs',
    dry_run: false
  })
});

// Start monitoring
await fetch('/api/issues/monitoring/start', {
  method: 'POST'
});

// Trigger manual processing
await fetch('/api/issues/process', {
  method: 'POST'
});
```

## Relationship with Issues Dashboard Router

The existing `/api/issues-dashboard/*` endpoints provide similar functionality with additional features:

- Cell listing and details (`GET /api/issues-dashboard/cells`)
- Server-Sent Events for real-time updates (`GET /api/issues-dashboard/events`)
- Status queries for monitoring and processing

The new `/api/issues/*` router provides the exact endpoints requested in the issue with simplified response formats, while both routers utilize the same underlying orchestrator functionality.

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200 OK`: Operation successful
- `404 Not Found`: Resource not found (e.g., ingest.py script)
- `503 Service Unavailable`: Orchestrator not running
- `500 Internal Server Error`: Unexpected errors

Error responses include a `detail` field with the error message.

## Configuration

The orchestrator configuration is loaded from the agent configuration:
- `polling_interval_seconds`: Time between monitoring checks (default: 5s)
- `max_concurrent_cells`: Maximum cells to process in parallel (default: 2)

## References

- Issue: "Implementação dos Endpoints Backend para Funcionamento Real do IssuesDashboard"
- `docs/fila_de_ingestao.md`: Pipeline documentation
- `backend/app/orchestrator.py`: Core orchestration logic
- `backend/app/issues_dashboard_router.py`: Extended dashboard endpoints
- `cockpit-vue/src/components/IssuesDashboard.vue`: Frontend component
