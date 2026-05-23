# Messages Cell

A read-only cell type for displaying inbox messages in the ScareVerse Dynamic Workspace.

## Purpose

Extract message display functionality from the Inbox Cell and Planet Hall viewer into a reusable cell type. This cell displays messages in read-only mode — no reply action included.

## Actions

| Action | HTTP | Description |
|--------|------|-------------|
| `list_messages` | `GET /api/inbox/messages` | List received messages |

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `cell` | `any` | `undefined` | Cell instance from DynamicWorkspace |
| `cellId` | `string` | `undefined` | Cell ID for standalone usage |
| `readOnly` | `boolean` | `true` | When `false`, emits `@reply` events |
| `messages` | `any[]` | `undefined` | External messages array for state sync |

## Events

| Event | Payload | Description |
|-------|---------|-------------|
| `reply` | `msg: any` | Emitted when user clicks Reply (only when `readOnly=false`) |

## API Dependencies

All endpoints are provided by the existing `backend/app/routers/inbox_router.py`. No new endpoints were created.

## Architecture

- **MessagesCell.ts**: BaseCell implementation with `list_messages` action via `apiFetch`
- **useMessagesCell.ts**: Composable encapsulating cell execution with reactive state
- **View.vue**: Vue component following the **Buffer Local Pattern** (REACTIVITY_ISOLATION.md)

## Directory Structure

```
cell_types/messages-cell/
├── type.json                               → Text pointer to notebook_item_types/messages-cell.json
├── frontend/
│   ├── MessagesCell.ts                     → BaseCell implementation
│   ├── View.vue                            → Vue component
│   ├── composables/
│   │   └── useMessagesCell.ts              → Reactive composable
│   ├── i18n/
│   │   ├── en.json                         → English translations
│   │   └── pt.json                         → Portuguese translations
│   └── tests/
│       └── MessagesCell.spec.ts            → Unit tests (≥90% coverage)
└── docs/
    └── README.md                           → This file
```
