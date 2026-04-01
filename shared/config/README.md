# Shared Configuration

Frontend configuration modules shared across all ScareVerseLab cell types and the cockpit-vue shell.

## Purpose

This directory centralizes API endpoint definitions, service configuration, and runtime limits so that individual cells do not hard-code URLs or tuning parameters. All cells import from here to ensure consistent configuration across the platform.

## Index

### Files

| File | Description |
|------|-------------|
| `apiConfig.js` | Base API URL, request timeout, and global Axios/fetch defaults |
| `chatLimits.js` | Message length limits, rate limits, and history window sizes for the Chat-IA cell |
| `endpoints.js` | Full map of all backend REST API endpoints (auth, cells, books, content, system, etc.) |

## Overview

### `apiConfig.js`

Exports the base API configuration object used by `apiService.ts` and individual service modules:

```js
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
export const REQUEST_TIMEOUT_MS = 30_000
```

### `endpoints.js`

Provides a structured map of every backend endpoint so that service modules reference named constants instead of raw strings:

```js
import { endpoints } from '@artifacts/shared/config/endpoints'

const url = endpoints.cells.list   // '/api/v1/cells/'
```

### `chatLimits.js`

Exports tuning constants for the Chat-IA cell to avoid magic numbers:

```js
export const MAX_MESSAGE_LENGTH = 4096
export const HISTORY_WINDOW = 20
```

## Usage

```js
import { API_BASE_URL, REQUEST_TIMEOUT_MS } from '@artifacts/shared/config/apiConfig'
import { endpoints } from '@artifacts/shared/config/endpoints'
import { MAX_MESSAGE_LENGTH } from '@artifacts/shared/config/chatLimits'
```

## Related Documentation

- [Shared Artifacts Root](../) - Overview of all shared artifacts
- [Shared Services](../services/) - Service modules that consume this configuration
- [Shared Composables](../composables/) - Composables that reference these endpoints
