# Shared Services

Frontend service modules shared across all ScareVerseLab cell types and the cockpit-vue shell.

## Purpose

This directory provides a centralized layer of HTTP/API service functions so that individual cells do not duplicate request logic. Each service module corresponds to a backend domain (auth, cells, books, issues, etc.) and exports typed functions for CRUD operations.

## Index

### Files

| File | Description |
|------|-------------|
| `apiService.ts` | Base HTTP client — wraps Axios with auth headers, error handling, and retry logic |
| `authService.js` | Authentication operations: login, logout, token refresh, session validation |
| `cellTypesService.js` | Fetches and caches the list of available cell types from the backend registry |
| `issuesDashboardService.js` | Data operations for the Issues Dashboard cell (fetch, filter, paginate issues) |
| `issuesService.js` | Generic issue CRUD: create, read, update, close GitHub-linked issues |
| `layoutBooksService.js` | Persists and retrieves book layout configurations |
| `layoutPersistence.js` | Low-level layout persistence helpers (IndexedDB / backend sync) |
| `notebookCellsService.js` | Notebook cell CRUD: create, read, update, delete, reorder cells within a notebook |
| `systemService.js` | System-level operations: health checks, version info, platform metadata |

## Overview

All service modules use `apiService.ts` as their HTTP transport. This means:

- Auth tokens are injected automatically via a request interceptor
- 401 responses trigger an automatic token refresh
- Network errors are normalized to a consistent error shape
- Base URL is read from `@artifacts/shared/config/apiConfig`

## Usage

```ts
import { authService } from '@artifacts/shared/services/authService'
import { notebookCellsService } from '@artifacts/shared/services/notebookCellsService'

// Login
const { access_token } = await authService.login({ username, password })

// Fetch cells for a notebook
const cells = await notebookCellsService.list(notebookId)
```

## Related Documentation

- [Shared Artifacts Root](../) - Overview of all shared artifacts
- [Shared Composables](../composables/) - Composables that wrap these services
- [Shared Config](../config/) - API URL and endpoint configuration
- [Backend API](../../../docs/official/backend/) - Backend API documentation
