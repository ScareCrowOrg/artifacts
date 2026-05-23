# Requests Cell

A read-only cell type for displaying incoming allowance/access requests in the ScareVerse Dynamic Workspace.

## Purpose

Extract request display functionality from the Inbox Cell and Planet Hall viewer into a reusable cell type. This cell displays requests in read-only mode — no approve/reject actions included.

## Actions

| Action | HTTP | Description |
|--------|------|-------------|
| `list_requests` | `GET /api/inbox/requests?direction=received` | List received requests |

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `cell` | `any` | `undefined` | Cell instance from DynamicWorkspace |
| `cellId` | `string` | `undefined` | Cell ID for standalone usage |
| `readOnly` | `boolean` | `true` | When `false`, emits `@approve`/`@reject` events |
| `requests` | `any[]` | `undefined` | External requests array for state sync |

## Events

| Event | Payload | Description |
|-------|---------|-------------|
| `approve` | `requestId: string` | Emitted when user clicks Approve (only when `readOnly=false`) |
| `reject` | `requestId: string` | Emitted when user clicks Reject (only when `readOnly=false`) |

## API Dependencies

All endpoints are provided by the existing `backend/app/routers/inbox_router.py`. No new endpoints were created.

## Architecture

- **RequestsCell.ts**: BaseCell implementation with `list_requests` action via `apiFetch`
- **useRequestsCell.ts**: Composable encapsulating cell execution with reactive state (also importable by planet-hall for `allowanceStatus` sync)
- **View.vue**: Vue component following the **Buffer Local Pattern** (REACTIVITY_ISOLATION.md)

## Directory Structure

```
cell_types/requests-cell/
├── type.json                               → Text pointer to notebook_item_types/requests-cell.json
├── frontend/
│   ├── RequestsCell.ts                     → BaseCell implementation
│   ├── View.vue                            → Vue component
│   ├── composables/
│   │   └── useRequestsCell.ts              → Reactive composable
│   ├── i18n/
│   │   ├── en.json                         → English translations
│   │   └── pt.json                         → Portuguese translations
│   └── tests/
│       └── RequestsCell.spec.ts            → Unit tests (≥90% coverage)
└── docs/
    └── README.md                           → This file
```
