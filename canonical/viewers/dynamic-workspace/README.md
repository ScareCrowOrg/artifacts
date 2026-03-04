# DynamicWorkspace v2 — Viewer

> **Phase 1**: Runner Integration & Cockpit ↔ Runner Handshake

## Overview

This viewer runs inside a Vite-served iframe at:

```
http://localhost:5052/viewers/dynamic-workspace
```

It is loaded by `ViewerShell.vue` (Cockpit) as an isolated micro-frontend context.

## Architecture

```
Cockpit-Vue (shell host)
  └── ViewerShell.vue
        └── <iframe src="http://localhost:5052/viewers/dynamic-workspace">
              └── App.vue  ← This package
```

## Handshake Protocol

### 1. Cockpit → Runner (`INIT_WORKSPACE`)

Sent by `useViewerHandshake.ts` after the iframe loads:

```typescript
{
  type: 'INIT_WORKSPACE',
  payload: {
    workspaceId: string,   // UUID from layout store
    sessionToken: string,  // JWT from authService
    cockpitOrigin: string, // window.location.origin
    userId: string,        // current user UUID
  },
  timestamp: number
}
```

### 2. Runner → Cockpit (`RUNNER_READY`)

Sent by `useWorkspaceHandshake.ts` after backend validation:

```typescript
{
  type: 'RUNNER_READY',
  payload: {
    workspaceId: string,
    runnerOrigin: string,       // window.location.origin
    version: 'v2.0.0-phase1',
    capabilities: ['hello-world'],
    status: 'ready',
  },
  timestamp: number
}
```

### 3. Error Case (`RUNNER_ERROR`)

```typescript
{
  type: 'RUNNER_ERROR',
  payload: {
    workspaceId: string,
    errorCode: string,  // 'INVALID_TOKEN' | 'VALIDATION_FAILED' | 'INVALID_PAYLOAD'
    message: string,
  },
  timestamp: number
}
```

## Files

| File | Purpose |
|------|---------|
| `App.vue` | Root Vue component (hello world + status display) |
| `composables/useWorkspaceHandshake.ts` | postMessage receiver + backend validation |
| `stores/workspaceStore.ts` | Pinia store for workspace state |
| `README.md` | This file |

## Backend Dependency

Validation calls `POST /api/workspace/validate-session` (CentralHub):

```json
// Request
{ "workspaceId": "uuid", "sessionToken": "jwt" }

// Response
{ "valid": true, "workspaceId": "uuid", "userId": "uuid", "permissions": ["read","write"] }
```

## Out of Scope (Phase 2+)

- Cell rendering
- Cell execution
- Layout persistence
- Multi-workspace support
