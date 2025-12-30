# Monitoring API Documentation

## Overview

The Monitoring API provides endpoints for accessing pipeline monitoring data, including prerequisites validation, component health checks, and aggregated metrics. It also supports real-time updates via WebSocket streaming.

**Base URL**: `/api/v1/monitoring`

---

## REST API Endpoints

### 1. Get Pipeline Health

**Endpoint**: `GET /api/v1/monitoring/pipeline/health`

**Description**: Returns the health status of all pipeline components.

**Response**:
```json
{
  "status": "healthy" | "degraded" | "unhealthy" | "unknown",
  "components": [
    {
      "component": "frontend",
      "status": "healthy",
      "latency_ms": 12.5,
      "details": {},
      "timestamp": 1735550000.0
    }
  ],
  "timestamp": 1735550000.0
}
```

**Status Codes**:
- `200`: Success
- `500`: Internal server error

---

### 2. Get Prerequisites

**Endpoint**: `GET /api/v1/monitoring/pipeline/prerequisites`

**Description**: Returns validation status of all 24 pipeline prerequisites.

**Response**:
```json
{
  "prerequisites": [
    {
      "id": "frontend.use_cell_factory",
      "name": "useCellFactory Composable",
      "category": "frontend",
      "status": "healthy",
      "criticality": "critical",
      "validation_method": "import_check",
      "monitoring_available": true,
      "details": {"available": true},
      "timestamp": 1735550000.0
    }
  ],
  "summary": {
    "total": 24,
    "healthy": 20,
    "degraded": 2,
    "unhealthy": 1,
    "unknown": 1
  }
}
```

**Categories**: frontend, extension, wasm, backend, infrastructure, configuration, runtime

**Status Codes**:
- `200`: Success
- `500`: Internal server error

---

### 3. Get Metrics

**Endpoint**: `GET /api/v1/monitoring/pipeline/metrics`

**Description**: Returns aggregated metrics for dashboard visualization.

**Response**:
```json
{
  "generation_metrics": {
    "total_generations": 150,
    "success_rate": 95.5,
    "avg_generation_time_ms": 2450.0,
    "active_generations": 3
  },
  "component_health": {
    "frontend": "healthy",
    "extension": "healthy",
    "backend": "degraded"
  },
  "latency_metrics": {
    "extension_latency_p50_ms": 45.2,
    "extension_latency_p95_ms": 120.5,
    "extension_latency_p99_ms": 250.0
  },
  "resource_metrics": {
    "opfs_quota_used_percent": 35.5,
    "opfs_available_mb": 512.0
  },
  "timestamp": 1735550000.0
}
```

**Status Codes**:
- `200`: Success
- `500`: Internal server error

---

### 4. Get Complete Monitoring Data

**Endpoint**: `GET /api/v1/monitoring/pipeline`

**Description**: Returns complete monitoring data (prerequisites, health, metrics) in a single request.

**Response**:
```json
{
  "prerequisites": [...],
  "components": [...],
  "metrics": {...},
  "summary": {
    "overall_status": "healthy",
    "prerequisites_healthy": 23,
    "prerequisites_total": 24,
    "components_healthy": 7,
    "components_total": 7
  }
}
```

**Status Codes**:
- `200`: Success
- `500`: Internal server error

---

### 5. Start Health Monitoring

**Endpoint**: `POST /api/v1/monitoring/pipeline/health/start`

**Description**: Starts periodic health checks for all components.

**Response**:
```json
{
  "status": "started",
  "message": "Health check monitoring started",
  "interval_seconds": 30
}
```

**Status Codes**:
- `200`: Success
- `500`: Internal server error

---

### 6. Stop Health Monitoring

**Endpoint**: `POST /api/v1/monitoring/pipeline/health/stop`

**Description**: Stops periodic health checks.

**Response**:
```json
{
  "status": "stopped",
  "message": "Health check monitoring stopped"
}
```

**Status Codes**:
- `200`: Success
- `500`: Internal server error

---

## WebSocket Streaming

### Connection

**Endpoint**: `ws://host/api/v1/ws/event-bus?token=<jwt_token>`

**Authentication**: JWT token required in query parameter

### Event Types

#### 1. Health Update
**Topic**: `monitoring/health/update`

**Payload**:
```json
{
  "components": [
    {
      "component": "frontend",
      "status": "healthy",
      "latency_ms": 12.5,
      "details": {},
      "timestamp": 1735550000.0
    }
  ],
  "timestamp": 1735550000.0
}
```

#### 2. Metrics Update
**Topic**: `monitoring/metrics/update`

**Payload**:
```json
{
  "generation_metrics": {...},
  "component_health": {...},
  "latency_metrics": {...},
  "resource_metrics": {...},
  "timestamp": 1735550000.0
}
```

#### 3. Prerequisite Update
**Topic**: `monitoring/prerequisite/update`

**Payload**:
```json
{
  "prerequisites": [...],
  "summary": {
    "total": 24,
    "healthy": 20,
    "degraded": 2,
    "unhealthy": 1,
    "unknown": 1
  }
}
```

#### 4. Alert Triggered
**Topic**: `monitoring/alert/triggered`

**Payload**:
```json
{
  "alert_id": "alert-123",
  "severity": "critical" | "warning" | "info",
  "title": "Component Unhealthy",
  "message": "Frontend component is not responding",
  "details": {
    "component": "frontend",
    "latency_ms": 5000
  },
  "triggered_at": "2025-12-30T08:00:00Z"
}
```

#### 5. Alert Resolved
**Topic**: `monitoring/alert/resolved`

**Payload**:
```json
{
  "alert_id": "alert-123",
  "resolution_details": {
    "resolved_by": "auto-recovery",
    "duration_seconds": 120
  },
  "resolved_at": "2025-12-30T08:02:00Z"
}
```

### Heartbeat

**Topic**: `system/event/heartbeat`

**Client → Server**:
```json
{
  "source": "monitoring-dashboard",
  "topic": "system/event/heartbeat",
  "payload": {
    "status": "alive",
    "timestamp": 1735550000000
  }
}
```

**Server → Client**:
```json
{
  "source": "backend-websocket-server",
  "topic": "system/event/heartbeat",
  "payload": {
    "status": "healthy",
    "client_id": "user-123"
  }
}
```

---

## Error Responses

All endpoints follow a consistent error response format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Status Codes**:
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (missing/invalid authentication)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (endpoint doesn't exist)
- `500`: Internal Server Error (unexpected error)

---

## Rate Limiting

- REST API: No explicit rate limiting (relies on FastAPI defaults)
- WebSocket: Connection limit per user (configurable)
- Event Publishing: Throttled to prevent spam (max 10 events/second per type)

---

## Examples

### cURL Examples

#### Get Health Status
```bash
curl -X GET http://localhost:8000/api/v1/monitoring/pipeline/health \
  -H "Authorization: Bearer <token>"
```

#### Start Health Monitoring
```bash
curl -X POST http://localhost:8000/api/v1/monitoring/pipeline/health/start \
  -H "Authorization: Bearer <token>"
```

### JavaScript/Fetch Examples

#### Get Complete Monitoring Data
```javascript
const response = await fetch('/api/v1/monitoring/pipeline', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})

if (response.ok) {
  const data = await response.json()
  console.log('Overall status:', data.summary.overall_status)
}
```

#### WebSocket Connection
```javascript
const token = localStorage.getItem('auth_token')
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/event-bus?token=${token}`)

ws.onmessage = (event) => {
  const message = JSON.parse(event.data)
  
  if (message.topic === 'monitoring/alert/triggered') {
    console.log('Alert:', message.payload.title)
  }
}
```

---

## Troubleshooting

### API Returns 500 Error
- Check backend logs for exceptions
- Verify MongoDB/Redis connectivity
- Ensure all monitoring services are initialized

### WebSocket Connection Fails
- Verify JWT token is valid and not expired
- Check Redis is running and accessible
- Ensure REDIS_ENABLED=true in environment

### No Real-Time Updates
- Verify health monitoring is started (`/pipeline/health/start`)
- Check WebSocket connection state
- Confirm subscription to correct event topics

### Alerts Not Displaying
- Verify alert conditions are met
- Check WebSocket event handlers are registered
- Ensure AlertBanner component is mounted

---

## Support

For issues or questions:
- Check Sprint 3 Completion Report for implementation details
- Review test files for usage examples
- Consult troubleshooting guide above

**Last Updated**: 2025-12-30  
**API Version**: 1.0.0  
**Sprint**: Sprint 3 - API Integration
