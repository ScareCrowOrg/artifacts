---
processed: true
processed_date: "2026-01-20"
generated_docs:
  - "docs/official/frontend/architecture/cell-type-examples-patterns.md"
themes:
  - "cell-architecture"
  - "redis"
  - "data-management"
  - "hierarchical-navigation"
modules:
  - "frontend"
  - "artifacts"
  - "infrastructure"
code_verified: true
dead_docs_found: false
---

# Redis Explorer Cell

## Overview

The **Redis Explorer Cell** provides a hierarchical, interactive interface for exploring and managing Redis keys in the ScareVerse ecosystem. It enables developers to debug Redis state, inspect key values, and safely invalidate key branches for testing and development.

## Features

### 🔍 Hierarchical Navigation
- **SCAN-based exploration**: Uses non-blocking `SCAN` command instead of `KEYS` to avoid blocking Redis
- **Prefix-based grouping**: Navigate through Redis keyspace like a filesystem
- **Breadcrumb navigation**: Easy backtracking through the key hierarchy
- **3-click goal**: Reach any key from root in less than 3 clicks

### 📊 Key Inspection
- **Automatic JSON parsing**: Values are automatically parsed and formatted as JSON when possible
- **Type detection**: Supports all Redis data types (string, hash, list, set, zset)
- **Metadata display**: Shows key type, TTL, and memory size
- **Copy to clipboard**: One-click copying of keys and values

### 🗑️ State Invalidation
- **Pattern-based deletion**: Delete entire branches of keys by prefix
- **Two-step confirmation**: Dry-run preview followed by explicit confirmation
- **Safety modal**: Shows affected keys and requires explicit confirmation
- **Audit logging**: All deletions are logged with user context

### 📈 Redis Statistics
- **Server info**: Redis version, memory usage, key count
- **Real-time updates**: Refresh after operations
- **Health monitoring**: Connection status indicator

## Usage

### Basic Navigation

1. **Start at Root**: The cell opens at the root level showing top-level prefixes
2. **Drill Down**: Click on any branch (📁) to explore that prefix
3. **View Keys**: Click on any key (🔑) to inspect its value
4. **Navigate Back**: Use breadcrumb navigation or click "Root" to return

### Key Patterns

Redis keys in ScareVerse follow a hierarchical naming convention with `:` as the delimiter:

```
aider:session:123:data
ollama:job:456:status
sd:generation:789:result
```

The explorer breaks these down into navigable segments:
- Root → `aider`, `ollama`, `sd`
- `aider` → `session`, `job`
- `aider:session` → `123`, `456`
- `aider:session:123` → Final keys

### Deleting Keys

**⚠️ DESTRUCTIVE OPERATION - Use with caution!**

1. Navigate to the prefix you want to delete
2. Click "🗑️ Delete Branch" button
3. Review the preview showing affected keys
4. Click "Delete" to confirm

The deletion removes **ALL** keys matching the prefix pattern. Always use the preview step first!

### Example Workflows

#### Debug Session State
```
1. Navigate to "aider" → "session"
2. Find your session ID (e.g., "test-123")
3. Click to view session data
4. Inspect state and troubleshoot issues
```

#### Clean Test Data
```
1. Navigate to "aider" → "session" → "test"
2. Click "Delete Branch"
3. Preview shows all test session keys
4. Confirm to clean up test data
```

#### Monitor Job Status
```
1. Navigate to "ollama" → "job"
2. Browse active job IDs
3. Click job to view status and progress
4. Monitor completion
```

## Properties

### category (string)
- **Type**: `string`
- **Default**: `"ephemeral"`
- **Description**: Cell category - this is an ephemeral cell (not persisted)

### title (string)
- **Type**: `string`
- **Default**: `"Redis Explorer"`
- **Description**: Cell display title

### current_prefix (string)
- **Type**: `string`
- **Default**: `""`
- **Description**: Current Redis key prefix being explored

### delimiter (string)
- **Type**: `string`
- **Default**: `":"`
- **Description**: Delimiter for hierarchical structure

### max_depth (integer)
- **Type**: `integer`
- **Default**: `1`
- **Description**: Maximum depth levels to display at once

## API Integration

The cell uses the following backend endpoints:

### `GET /api/v1/redis-explorer/info`
Get Redis server information and statistics.

### `POST /api/v1/redis-explorer/scan`
Scan keys hierarchically by prefix.

Request:
```json
{
  "prefix": "aider:session",
  "delimiter": ":",
  "max_depth": 1
}
```

### `GET /api/v1/redis-explorer/key/{key}`
Get value of a specific Redis key.

### `POST /api/v1/redis-explorer/delete`
Delete keys matching a prefix pattern.

Request:
```json
{
  "prefix": "aider:session:test:",
  "dry_run": true,
  "confirm": false
}
```

## Technical Details

### Performance
- **Non-blocking**: Uses `SCAN` with `count=100` to avoid blocking Redis
- **Efficient deletion**: Uses Redis pipeline for batch deletions
- **Pagination**: Supports cursor-based iteration for large keysets

### Security
- **Authentication required**: All endpoints require valid JWT token
- **Explicit confirmation**: Deletions require `confirm: true` flag
- **Audit trail**: All operations logged with user ID

### TypeScript Implementation
- **Full type safety**: All component logic is TypeScript
- **Typed interfaces**: Request/response models defined
- **Type-safe refs**: Explicit type annotations for reactive state

## Best Practices

### 1. Use Dry Run First
Always preview deletions before confirming:
```typescript
// First: dry_run = true to preview
// Then: dry_run = false, confirm = true to delete
```

### 2. Naming Conventions
Follow hierarchical naming for better navigation:
```
✅ Good: service:resource:id:attribute
❌ Bad: service_resource_id_attribute
```

### 3. TTL for Temporary Data
Set appropriate TTLs on temporary keys to avoid manual cleanup:
```
aider:session:temp:*  (TTL: 1 hour)
ollama:job:*          (TTL: 24 hours)
```

### 4. Limit Prefix Scope
When deleting, use the most specific prefix possible:
```
✅ Specific: aider:session:test:123:
❌ Too Broad: aider:session:
```

## Troubleshooting

### "Redis is not available"
- Check Redis is running: `make redis-status`
- Verify `REDIS_ENABLED=true` in `.env`
- Check Redis connection parameters

### "Failed to scan keys"
- Verify authentication token is valid
- Check Redis connection health at `/api/v1/redis-explorer/health`
- Review backend logs for Redis errors

### "No keys found"
- Verify you're looking at the correct prefix
- Check if keys have expired (check TTL)
- Use Redis CLI to verify: `redis-cli KEYS pattern*`

### Cell not loading
- Verify cell type is registered: Check backend startup logs
- Ensure `type.json` symlink is correct
- Check for TypeScript errors: `npm run type-check`

## Related Documentation

- [RULESET.md Rule 4.5](../../../docs/official/RULESET.md#45-typescript-for-new-frontend-code) - TypeScript requirements
- [ADDING_NEW_CELL_TYPE.md](../../../docs/official/ADDING_NEW_CELL_TYPE.md) - Cell architecture guide
- [Redis Client Documentation](../../../backend/app/core/redis_client.py) - Redis integration

## Support

For issues or questions:
- Open an issue with label `redis-explorer`
- Check backend logs for Redis service errors
- Review network requests in browser DevTools

---

**Version**: 1.0.0  
**Last Updated**: 2026-01-19  
**Cell Type ID**: `redis-explorer`
