---
processed: true
processed_date: 2025-12-08
themes:
  - api
  - file-sharing
  - ngrok
  - networking
modules:
  - backend
  - api
code_verified: true
dead_docs_found: false
---
# Ngrok Share Module

## Overview

This module provides functionality for temporarily sharing files and folders from the ScareVerse repository via ngrok tunnels. It enables secure, temporary public access to local files through dynamically created HTTP servers and ngrok tunnels.

## Architecture

The ngrok module is organized into four main components:

### 1. **models.py** - Pydantic Request Models
- `ShareStartRequest`: Request model for starting a file share
- `ShareAddRequest`: Request model for adding files to an active share
- `ShareRemoveRequest`: Request model for removing files from an active share

### 2. **state.py** - Global State Management
- Manages the state of active ngrok tunnels
- Tracks:
  - Tunnel activation status
  - Public URLs
  - Processes (ngrok and HTTP server)
  - Temporary directories
  - Shared files list

### 3. **helpers.py** - Business Logic Functions
- `get_temp_share_dir()`: Creates/gets temporary directory for file sharing
- `copy_file_to_share()`: Copies files/directories to share directory
- `remove_file_from_share()`: Removes files/directories from share
- `start_ngrok_tunnel()`: Starts ngrok tunnel and retrieves public URL
- `stop_ngrok_tunnel()`: Stops active ngrok tunnel
- `cleanup_share()`: Cleans up temporary files and resets state
- `start_http_server()`: Starts Python HTTP server for share directory

### 4. **__init__.py** - Public API
- Exports all public models, functions, and state accessors
- Provides clean interface for the main router file

## File Structure

```
backend/app/routers/ngrok/
├── __init__.py          # Public API exports
├── models.py            # Pydantic request models
├── state.py             # Global state management
├── helpers.py           # Helper functions
└── README.md            # This file
```

## Usage

The ngrok module is consumed by the main router file (`ngrok_router.py`) which defines the FastAPI endpoints:

```python
from .ngrok.models import ShareStartRequest
from .ngrok.state import get_ngrok_state, set_ngrok_active
from .ngrok.helpers import start_ngrok_tunnel, cleanup_share

# Use in endpoints
@ngrok_router.post("/share/start")
async def share_start(request: ShareStartRequest):
    state = get_ngrok_state()
    success, public_url, error = start_ngrok_tunnel()
    # ...
```

## API Endpoints

The main router exposes the following endpoints:

- **POST /share/start** - Start ngrok tunnel and share files
- **POST /share/add** - Add files to active share
- **POST /share/remove** - Remove files from active share
- **POST /share/stop** - Stop ngrok tunnel
- **GET /share/status** - Get current share status

## Security Considerations

1. **Path Validation**: All file paths are validated using `validate_and_sanitize_path()` before operations
2. **Secure Permissions**: Temporary directories are created with mode `0o700` (owner-only access)
3. **CodeQL Alerts**: Path injection alerts are documented as false positives with justification
4. **Error Handling**: Stack traces are not exposed to users in error responses

## Dependencies

- **External Tools**: Requires `ngrok` to be installed and available in PATH
- **Python Packages**: 
  - `requests` - For querying ngrok API
  - Standard library: `subprocess`, `shutil`, `pathlib`, `tempfile`

## Configuration

The module uses the following environment variables:

- `NGROK_API_URL` - Ngrok API endpoint (default: `http://localhost:4040`)

## Testing

Tests should cover:

1. **Unit Tests** (helpers.py):
   - Directory creation
   - File copy/remove operations
   - State management functions

2. **Persistence Tests**:
   - Temporary directory cleanup
   - File system operations

3. **Integration Tests**:
   - Full endpoint flows
   - Error scenarios (ngrok not installed, invalid paths, etc.)

## Maintenance Notes

- **File Limits**: All files in this module should remain under 500 lines
- **Modularization**: If any file grows beyond 500 lines, further split into submodules
- **Documentation**: Keep this README updated when adding new functionality

## Related Files

- `backend/app/routers/ngrok_router.py` - Main router using this module
- `backend/app/file_utils.py` - Path validation utilities
- `backend/app/config.py` - Configuration including `SCAREFERA_LAB_DIR`
