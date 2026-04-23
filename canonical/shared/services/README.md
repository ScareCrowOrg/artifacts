# Shared Services

Reusable service utilities shared across all ScareVerse canonical services, providing Redis heartbeat registration and job routing capabilities.

## Purpose

This directory provides shared Python modules used by multiple canonical services:
- **BaseService**: Reusable Redis L1 heartbeat registration for service self-discovery
- Enables GateKeeper and service-discovery.py to detect running services dynamically
- Follows the fire-and-forget heartbeat pattern used across all ScareVerse services

## Directory Structure

```
services/
├── __init__.py         - Python package marker
└── base_service.py     - BaseService class with Redis L1 heartbeat registration
```

## How to Use

```python
import asyncio
from canonical.shared.services.base_service import BaseService
from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def startup():
    service = BaseService("my-service", service_port=8080)
    asyncio.create_task(service.heartbeat())
```

### Redis Key Format

BaseService writes to Redis L1 with the following key and value:

```
Key:   state:service:{service_name}:available
Value: {"port_opened": true|false|null, "timestamp": 1713085200.123}
TTL:   key_ttl seconds (default: 3× heartbeat_interval)
```

### Health Check Behavior

| `port_opened` value | Meaning |
|---|---|
| `true` | HTTP GET /health returned 200 (service healthy) |
| `false` | Port not responding or health check failed |
| `null` | No port configured (existence-only registration) |

## Content Index

| File | Description |
|---|---|
| `__init__.py` | Python package marker |
| `base_service.py` | BaseService class with Redis L1 heartbeat and health check |
