# 3D Mesh Prototyping Cell – Frontend Composables

## Purpose

Vue 3 composables for the **3D Mesh Prototyping Cell** frontend.

## Content Index

| File | Description |
|------|-------------|
| [`useJobPolling.ts`](./useJobPolling.ts) | `useJobPolling()` — Redis-based job status polling with configurable intervals; polls Backend for job state transitions (`queued` → `processing` → `completed`/`failed`) |

## How to Use

```typescript
import { useJobPolling } from './composables/useJobPolling'

const { jobStatus, startPolling, stopPolling } = useJobPolling()
await startPolling(jobId, { interval: 2000, maxRetries: 30 })
```

## Related

- [`../`](../) — 3D Mesh Prototyping Cell frontend root
- [`../../../backend/scripts/`](../../../backend/scripts/) — Backend where job queue runs
