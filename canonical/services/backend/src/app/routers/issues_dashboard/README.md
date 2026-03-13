---
processed: true
processed_date: 2025-12-08
themes:
  - api
  - dashboard
  - issues
  - sse
  - streaming
modules:
  - backend
  - api
code_verified: true
dead_docs_found: false
---
# Issues Dashboard Module

## Overview

The Issues Dashboard module provides comprehensive reactive monitoring and management capabilities for the ScareVerse issues-queue. It implements a real-time dashboard with Server-Sent Events (SSE) streaming, orchestrator control, and manual processing triggers.

## Purpose

Monitor and manage cells in the issues-queue book (`book-issues-queue-v1`) that represent ingestion issues requiring attention. The module provides:

- **Real-time Monitoring**: SSE streams for cell state changes and fragment updates
- **Orchestrator Control**: Start/stop monitoring loops, pause/resume processing
- **Manual Triggers**: Force immediate processing or trigger ingest operations
- **Pagination & Filtering**: Browse issues with status filters and pagination

## Module Structure

```
issues_dashboard/
├── __init__.py          # Module exports and public API
├── models.py            # Pydantic request/response models
├── streaming.py         # SSE streaming implementations
├── helpers.py           # Business logic and helper functions
└── README.md            # This file
```

### File Descriptions

#### `__init__.py` (56 lines)
Module initialization and public API exports. Provides centralized access to all models, streaming functions, and helpers.

#### `models.py` (80 lines)
Pydantic models for API request/response validation:
- `IssueCounts`: Issue counts by status (pendente, executando, finalizado, erro)
- `PaginatedResponse[T]`: Generic paginated response with issue counts
- `TriggerIngestRequest/Response`: Ingest script trigger models
- `ProcessPendingCellsResponse`: Manual processing trigger response
- `MonitoringStatusResponse/ControlResponse`: Monitoring status and control
- `ProcessingStatusResponse/ControlResponse`: Processing status and control

#### `streaming.py` (337 lines)
Server-Sent Events (SSE) streaming implementations:
- `stream_events()`: General event bus streaming (cell state changes, fragments)
- `stream_cell_fragments()`: Redis-based streaming for individual cell fragments
- `stream_all_active_fragments()`: Pattern-based streaming for all active cells

**Technologies**:
- Event Bus subscriptions for internal events
- Redis pub/sub for real-time fragment streaming
- Async generators for SSE implementation
- Connection lifecycle management (keepalive, cleanup)

#### `helpers.py` (184 lines)
Business logic and helper functions:
- `get_filtered_cells_and_counts()`: Cell retrieval with filtering and pagination
- `get_cell_by_id()`: Single cell retrieval with validation
- `trigger_ingest_script()`: Subprocess management for ingest.py
- `get_orchestrator_or_raise()`: Orchestrator instance validation

**Key Features**:
- Filters cells by type (`ingestion-issue`) and book (`book-issues-queue-v1`)
- Calculates issue counts across all statuses
- Applies optional status filters (pendente, executando, finalizado, erro)
- Implements pagination with bounds checking

## API Endpoints

All endpoints are mounted at `/issues-dashboard` prefix.

### Cell Management

- `GET /cells` - List cells with pagination and filtering
  - Query params: `page`, `limit`, `status`
  - Returns: `PaginatedResponse[Celula]` with issue counts
  
- `GET /cells/{cell_id}` - Get cell details
  - Returns: `Celula` object

### Ingest Control

- `POST /ingest/trigger` - Trigger ingest.py script
  - Request: `TriggerIngestRequest` (source_dir, dry_run)
  - Returns: `TriggerIngestResponse` with PID and command

### Processing Control

- `POST /process-pending-cells` - Force immediate processing
  - Returns: `ProcessPendingCellsResponse` with pending count

### Monitoring Control

- `GET /monitoring/status` - Get monitoring status
- `POST /monitoring/start` - Start monitoring loop
- `POST /monitoring/stop` - Stop monitoring loop

### Processing State Control

- `GET /processing/status` - Get processing status (paused/active)
- `POST /processing/pause` - Pause cell processing
- `POST /processing/resume` - Resume cell processing

### Streaming Endpoints (SSE)

- `GET /events` - Stream general events (event bus)
- `GET /cells/{cell_id}/stream-fragments` - Stream cell fragments (Redis)
- `GET /stream-all-active-fragments` - Stream all active fragments (Redis pattern)

## Dependencies

### Internal Dependencies
- `app.models.Celula`: Cell data model
- `app.database.db`: Database access layer
- `app.config.BASE_DIR`: Project root path configuration
- `app.orchestrator.get_orchestrator_instance()`: Orchestrator singleton
- `app.event_bus.event_bus`: Internal event bus for pub/sub

### External Dependencies
- `FastAPI`: Web framework (APIRouter, HTTPException, Request, Query)
- `Pydantic`: Data validation (BaseModel, GenericModel)
- `redis.asyncio`: Redis async client for SSE streaming
- `subprocess`: Process management for ingest script

### Configuration Requirements
- `REDIS_ENABLED`: Boolean flag to enable/disable Redis streaming
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`: Redis connection config

## Usage Examples

### Listing Issues with Status Filter

```python
# Get all pending issues
GET /issues-dashboard/cells?status=pendente&page=1&limit=20

# Response includes issue counts across all statuses
{
  "items": [...],
  "total_items": 15,
  "total_pages": 1,
  "current_page": 1,
  "items_per_page": 20,
  "issue_counts": {
    "pendente": 15,
    "executando": 3,
    "finalizado": 42,
    "erro": 2
  }
}
```

### Streaming Cell Fragments (SSE)

```javascript
// Frontend EventSource example
const eventSource = new EventSource('/issues-dashboard/cells/abc123/stream-fragments');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.event_type === 'fragment') {
    console.log('Fragment received:', data.fragment);
  }
};
```

### Triggering Ingest

```python
POST /issues-dashboard/ingest/trigger
{
  "source_dir": "/path/to/source",
  "dry_run": false
}

# Response
{
  "status": "started",
  "message": "Ingest process started (PID: 12345)",
  "command": "python /path/to/ingest.py --source-dir /path/to/source"
}
```

## Testing Strategy

### Unit Tests
- Test helper functions in isolation (filtering, pagination logic)
- Mock database and orchestrator dependencies
- Validate error handling and edge cases

### Integration Tests
- Test endpoints with FastAPI TestClient
- Use mongomock for database simulation
- Validate request/response schemas

### SSE Streaming Tests
- Test event bus subscription lifecycle
- Mock Redis pub/sub for fragment streaming
- Validate connection handling and cleanup

## Security Considerations

- All orchestrator operations validate instance availability
- Error messages sanitized to avoid internal detail exposure
- Redis connection errors handled gracefully
- Subprocess execution limited to ingest.py script only
- File path validation via BASE_DIR to prevent path traversal

## Performance Notes

- Pagination implemented to avoid loading all cells in memory
- Issue counts calculated once per request for efficiency
- SSE keepalive pings every 30 seconds to maintain connections
- Redis streaming uses pattern subscription for scalability

## Future Enhancements

- [ ] Add WebSocket alternative to SSE for bidirectional communication
- [ ] Implement filtering by date range or cell content
- [ ] Add bulk operations (pause/resume multiple cells)
- [ ] Enhanced monitoring metrics (throughput, error rates)
- [ ] Export capabilities (CSV, JSON) for issue reports

## Related Documentation

- [Parent Routers README](../README.md) - Overview of all API routers
- [ARQUITETURA_TESTES.md](../../../../docs/ARQUITETURA_TESTES.md) - Testing architecture
- [RULESET.md](../../../../RULESET.md) - Project rules and conventions
