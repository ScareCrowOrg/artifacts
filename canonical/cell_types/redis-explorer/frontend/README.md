# Redis Explorer Cell – Frontend

## Purpose

Vue 3 frontend for the **Redis Explorer Cell** — interactive UI for exploring and managing Redis keys. Supports hierarchical key navigation by prefix, value inspection, TTL display, and key deletion.

## Content Index

| File | Description |
|------|-------------|
| [`RedisExplorerCell.ts`](./RedisExplorerCell.ts) | BaseCell implementation — `scan-keys`, `inspect-key`, `delete-key`, `server-info` actions; UI-first design |
| [`View.vue`](./View.vue) | Main component — prefix tree navigation, key inspector panel, server info sidebar, search/filter |

## Related

- [`../`](../) — Redis Explorer Cell root
- [`../backend/`](../backend/) — Backend for programmatic/ephemeral access
