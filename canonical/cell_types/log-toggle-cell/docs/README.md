---
processed: true
processed_date: 2026-01-13
updated_docs:
  - docs/official/frontend/features/log-toggle-cell.md
themes:
  - cell-types
  - debugging
  - logging
  - frontend
modules:
  - frontend
  - cell-types
code_verified: true
dead_docs_found: false
---
# Log Toggle Cell

## Overview

The **Log Toggle Cell** provides a user-friendly interface for temporarily enabling/disabling specific log namespaces during a session. This is particularly useful for debugging, performance analysis, and focusing on specific logs without being overwhelmed by irrelevant information.

**⚠️ Important**: This cell currently controls **frontend browser console logs only** (Vue.js application). It does not affect backend Python logging, which uses a different system.

**🔄 Ephemeral Cell**: This cell is marked as `"category": "ephemeral"`, which means instances created from this cell type will **NOT persist in the database**. Cell configuration exists only during the active session and is automatically cleared when the session ends or the service restarts. This is intentional for debugging/utility cells.

**🔗 Symlink Architecture**: Following ScareVerse conventions, the canonical cell type definition is stored in `artifacts/canonical/notebook_item_types/log-toggle-cell.json` and symlinked from `artifacts/canonical/cell_types/log-toggle-cell/type.json`.

**Key Features**:
- ✅ Temporarily activate/deactivate log namespaces
- ✅ Session-based configuration (non-persistent)
- ✅ Real-time log control without system restart
- ✅ Search and filter namespaces
- ✅ Bulk enable/disable operations
- ✅ Visual feedback for active logs
- ✅ Ephemeral instances (no database persistence)

## Properties

### category (string)

- **Type**: String
- **Default**: `"ephemeral"`
- **Description**: Cell category marker - `"ephemeral"` indicates this cell does not persist in the database
- **Values**: `"ephemeral"` (non-persistent), `"persistida"` (persistent), `"volatil"` (volatile)
- **Note**: Log toggle cells should always remain ephemeral for debugging purposes

### enabled_namespaces (array)

- **Type**: Array of strings
- **Default**: `[]`
- **Description**: List of log namespaces currently enabled for logging
- **Example**: `["auth", "api:cells", "store:*"]`

### debug_pattern (string)

- **Type**: String
- **Default**: `""`
- **Description**: Current DEBUG environment pattern representing all enabled namespaces
- **Format**: Comma-separated list or wildcard pattern
- **Examples**: 
  - `"auth,api"` - Enable auth and api namespaces
  - `"auth:*"` - Enable all auth sub-namespaces
  - `"*"` - Enable all logs

## Frontend Component

**Location**: `frontend/View.vue`

**Technology**: Vue 3 with TypeScript (Composition API)

### Component Features

1. **Namespace List**: Displays all available log namespaces with checkboxes
2. **Search Filter**: Quickly find specific namespaces
3. **Quick Actions**: 
   - Enable All: Activates all available namespaces
   - Disable All: Deactivates all namespaces
   - Apply Changes: Commits the configuration
4. **Visual Indicators**: Shows active namespace count and current DEBUG pattern
5. **Change Detection**: Apply button only enabled when changes are pending

### Component Props

```typescript
interface Props {
  cell: {
    initial_data?: {
      enabled_namespaces?: string[]
      debug_pattern?: string
    }
  }
}
```

### Component Events

- `update:cell`: Emitted when log configuration changes are applied

## Backend Scripts

**Location**: `backend/scripts/main.py`

### Functions

#### `execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]`

Processes log toggle requests and returns current configuration state.

**Parameters**:
- `cell_data`: Dictionary containing enabled_namespaces and debug_pattern

**Returns**:
```python
{
    "success": True,
    "current_pattern": "auth,api,store",
    "enabled_namespaces": ["auth", "api", "store"],
    "message": "Log configuration updated: auth,api,store"
}
```

#### `get_available_namespaces() -> List[str]`

Returns list of all available log namespaces in the application.

**Returns**: List of namespace strings

#### `validate_namespace(namespace: str) -> bool`

Validates a namespace string format.

**Parameters**:
- `namespace`: Namespace string to validate

**Returns**: Boolean indicating validity

## How It Works

### Frontend Logger System

ScareVerse uses a namespace-based logging system located at `cockpit-vue/src/utils/logger.js`:

```javascript
import { createLogger } from '@/utils/logger'
const log = createLogger('auth:login')
log.debug('User attempting login', { username })
```

### DEBUG Environment Variable Control

Logs are controlled by the `VITE_DEBUG` or `DEBUG` environment variable:

- `DEBUG=*` - Enable all logs
- `DEBUG=auth,api` - Enable specific namespaces
- `DEBUG=auth:*` - Enable all auth sub-namespaces
- Production builds automatically disable all logs

### Centralized Namespace Management

The Log Toggle Cell fetches available namespaces from the backend API endpoint:

**API Endpoint**: `GET /api/v1/logs/namespaces`

This provides a single source of truth for log namespaces, eliminating duplication
between frontend and backend code.

The API can either return a curated default list or perform dynamic discovery
by scanning the frontend codebase for `createLogger()` calls:

- `GET /api/v1/logs/namespaces` - Returns default curated list (fast)
- `GET /api/v1/logs/namespaces?discover=true` - Scans codebase (slower but complete)

### Temporary Session-Based Configuration

The Log Toggle Cell allows runtime modification of log settings:

1. User opens the Log Toggle Cell
2. Cell fetches available namespaces from API automatically
3. User selects namespaces in the UI
4. Click "Apply Changes" to activate
5. Settings stored in session (Redis or in-memory)
6. Middleware applies DEBUG pattern to current session
7. Configuration cleared on session end or restart

## Usage Example

### Basic Usage

1. Add a Log Toggle Cell to your notebook
2. The cell displays all available log namespaces
3. Check/uncheck namespaces you want to enable
4. Click "Apply Changes" to activate the configuration
5. Observe logs appearing/disappearing in browser console

### Common Scenarios

**Debugging Authentication Flow**:
```
Enable: auth, auth:login, auth:logout
Pattern: auth:*
```

**Monitoring API Calls**:
```
Enable: api, api:cells, api:books
Pattern: api:*
```

**Tracking State Changes**:
```
Enable: store, store:cells, store:books
Pattern: store:*
```

**Full Debug Mode**:
```
Enable: All namespaces
Pattern: *
```

## Integration Requirements

### Backend API Endpoints (Implemented ✅)

The following endpoints have been implemented to support centralized namespace management:

#### `GET /api/v1/logs/namespaces`

Returns list of available log namespaces.

**Query Parameters**:
- `discover` (boolean, optional): If true, scans codebase for namespaces. Default: false.

**Response**:
```json
[
  "app",
  "auth",
  "auth:login",
  "api",
  "store",
  "component:cell",
  "service:websocket",
  "router",
  "debug"
]
```

#### `GET /api/v1/logs/namespaces/stats`

Returns statistics about log namespaces (default vs discovered).

**Response**:
```json
{
  "default_count": 28,
  "discovered_count": 45,
  "default_namespaces": ["app", "auth", ...],
  "discovered_namespaces": ["app", "auth", "feature:new", ...]
}
```

### Automatic Registry Discovery (Implemented ✅)

Cell type registry discovery is now automatically triggered when loading notebook item types.

**Integration Point**: `cockpit-vue/src/stores/notebookCells.js`

The `loadNotebookItemTypes()` function now:
1. Calls `POST /api/v1/notebook-item-types/registry/discover` automatically
2. Logs discovery results in development mode
3. Continues gracefully if discovery fails (non-critical)
4. Fetches updated list of notebook item types

This eliminates the need for manual registry discovery via action links or API calls.

### Future API Endpoints (To Be Implemented)

#### `GET /api/v1/logs/namespaces`

Returns list of available log namespaces.

**Response**:
```json
{
  "namespaces": [
    "app", "auth", "auth:login", "api", "store"
  ]
}
```

#### `POST /api/v1/logs/configure`

Updates temporary log configuration for current session.

**Request**:
```json
{
  "enabled_namespaces": ["auth", "api"],
  "debug_pattern": "auth,api"
}
```

**Response**:
```json
{
  "success": true,
  "current_pattern": "auth,api",
  "message": "Log configuration updated"
}
```

#### `GET /api/v1/logs/current`

Gets current log configuration for session.

**Response**:
```json
{
  "enabled_namespaces": ["auth", "api"],
  "debug_pattern": "auth,api"
}
```

### Redis Session Storage

Store temporary log configuration per session:

```python
# Key format: log_config:{session_id}
redis.setex(
    f"log_config:{session_id}",
    3600,  # 1 hour TTL
    json.dumps({
        "enabled_namespaces": ["auth", "api"],
        "debug_pattern": "auth,api"
    })
)
```

## Limitations

1. **Session-Based Only**: Configuration does not persist across sessions or restarts
2. **Client-Side Logs Only**: Primarily affects frontend browser console logs
3. **No Server-Side Python Logs**: Does not control backend Python logging (different system)
4. **Manual Refresh Required**: Some components may require page refresh to apply new log settings

## Future Enhancements

- [ ] Auto-discovery of log namespaces from codebase
- [ ] Save/load preset log configurations
- [ ] Backend Python log control integration
- [ ] Log level filtering (debug, info, warn, error)
- [ ] Log export functionality
- [ ] Real-time log viewer within the cell

## Testing

### Manual Testing Checklist

- [ ] Cell renders correctly in notebook
- [ ] All namespaces display in the list
- [ ] Search filter works correctly
- [ ] Enable All activates all namespaces
- [ ] Disable All clears all namespaces
- [ ] Individual namespace toggles work
- [ ] Apply Changes button enables only when changes exist
- [ ] Current DEBUG pattern displays correctly
- [ ] Active namespace count updates correctly

### Automated Tests

**Backend Tests**: `backend/tests/test_main.py`
- Test execute_cell function
- Test get_available_namespaces
- Test validate_namespace

**Frontend Tests**: `frontend/tests/View.spec.ts`
- Test component rendering
- Test namespace toggling
- Test search filtering
- Test bulk operations
- Test change detection

## References

- [Frontend Logger Documentation](../../../cockpit-vue/src/utils/logger.js)
- [ADDING_NEW_CELL_TYPE Guide](../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [RULESET.md Rule 4.7 - Advanced Logging System](../../../docs/official/RULESET.md#47-advanced-logging-system-for-frontend)

## Support

For issues or questions:
- Check the frontend logger implementation
- Review DEBUG environment variable configuration
- Consult ScareVerse development team

---

**Version**: 1.0.0  
**Last Updated**: 2026-01-13  
**Category**: Debugging & Utilities
