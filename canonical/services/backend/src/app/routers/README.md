---
processed: true
processed_date: 2025-12-08
themes:
  - api
  - routers
  - architecture
  - backend
modules:
  - backend
  - api
code_verified: true
dead_docs_found: false
---
# API Routers

API endpoint routers for the ScareVerse backend. All FastAPI routers are organized here by functional domain.

## Index

### Authentication & Authorization
- `auth_router.py` - OAuth2 authentication endpoints (login, callback, status)

### Content Management
- `cells_router.py` - Cell (artifact) management endpoints
- `books_router.py` - Book (notebook) management endpoints
- `chat_router.py` - AI chat processing endpoints

### File Operations
- `file_ops_router.py` - File operations (save, load, move, delete)
- `ngrok_router.py` - Public file sharing via ngrok tunnels (main router)
- `ngrok/` - Ngrok share module (modularized)
  - `models.py` - Pydantic request/response models
  - `state.py` - Global state management for tunnels
  - `helpers.py` - Tunnel and file management functions
  - `README.md` - Module documentation

### System & Configuration
- `config_router.py` - Application configuration management
- `system_router.py` - System information and monitoring
- `services_router.py` - External services management
- `ai_models_router.py` - AI model configuration and management
- `ollama_queue.py` - Ollama Queue Bridge with distributed queue processing (SCARE-042)

### User & Session Management
- `users_router.py` - User management endpoints
- `sessions_router.py` - Session management endpoints

### Issues & Dashboard
- `issues_router.py` - GitHub issues integration
- `issues_dashboard_router.py` - Issues dashboard API (main router)
- `issues_dashboard/` - Issues dashboard module (modularized)
  - `models.py` - Pydantic request/response models
  - `streaming.py` - SSE streaming implementations
  - `helpers.py` - Business logic and helper functions
  - `README.md` - Module documentation

### Observability
- `traces_router.py` - Conversation trace retrieval and export

### Legacy/Core
- `router.py` - Main router aggregation (legacy, to be deprecated)

## Router Conventions

All routers follow these FastAPI patterns:

### Structure
```python
from fastapi import APIRouter, Depends, HTTPException
from typing import List

router = APIRouter(prefix="/api/v1/resource", tags=["Resource"])

@router.get("/")
async def list_resources():
    """List all resources."""
    pass

@router.post("/")
async def create_resource(data: ResourceCreate):
    """Create a new resource."""
    pass

@router.get("/{resource_id}")
async def get_resource(resource_id: str):
    """Get a specific resource."""
    pass
```

### Modularization Pattern

When a router exceeds 500 lines (per RULESET.md), it should be modularized into a subdirectory:

```
router_name/
├── __init__.py          # Module exports
├── models.py            # Pydantic models
├── helpers.py           # Business logic
├── [specific_module].py # Domain-specific logic
└── README.md            # Module documentation
```

**Example**: The `issues_dashboard_router.py` (866 lines) was modularized into:
- `issues_dashboard_router.py` (407 lines) - Main router with endpoint definitions
- `issues_dashboard/models.py` (80 lines) - Request/response models
- `issues_dashboard/streaming.py` (337 lines) - SSE streaming logic
- `issues_dashboard/helpers.py` (184 lines) - Business logic helpers

**Example**: The `ngrok_router.py` (548 lines) was modularized into:
- `ngrok_router.py` (392 lines) - Main router with endpoint definitions
- `ngrok/models.py` (47 lines) - Request/response models
- `ngrok/state.py` (92 lines) - Global state management
- `ngrok/helpers.py` (273 lines) - Tunnel and file management functions

**Benefits**:
- Each file stays under 500-line limit
- Clear separation of concerns (endpoints, models, logic)
- Improved testability and maintainability
- Self-documenting structure with dedicated README

### Best Practices
- Use proper HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Request/response validation with Pydantic models
- Authentication middleware for protected endpoints
- Comprehensive error handling and logging
- OpenAPI documentation via docstrings
- Async endpoints for I/O operations

### Authentication
Protected endpoints use OAuth2 dependencies:
```python
from app.auth import get_current_user

@router.get("/protected")
async def protected_endpoint(current_user = Depends(get_current_user)):
    return {"user": current_user}
```

## Usage

### Registering Routers
Routers are registered in `main.py`:
```python
from app.routers.cells_router import cells_router

app.include_router(cells_router)
```

### Testing
Router tests are located in `tests/endpoints/backend/`:
- `test_*_router.py` - Endpoint tests for each router
- `test_*_endpoints.py` - Integration tests for endpoints

Run router tests:
```bash
pytest tests/endpoints/backend/test_cells_router.py -v
```

## Related Documentation

- [Main Application](../README.md) - Backend application overview
- [Authentication Guide](../../docs/auth/) - OAuth2 and JWT authentication
- [API Documentation](../../docs/api/) - Complete API reference
- [Testing Guide](../../docs/ARQUITETURA_TESTES.md) - Testing strategy

## Notes

- All routers must have comprehensive tests (target: 90% coverage)
- Keep routers focused on endpoint logic, delegate to services
- Maximum 500 lines per router file (RULESET.md compliance)
- Use English for technical names (functions, parameters, endpoints)
- Documentation and comments can be in Portuguese
