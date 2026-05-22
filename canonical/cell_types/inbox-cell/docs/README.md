# Inbox Cell

An inbox cell type for the ScareVerse Dynamic Workspace that allows planet owners to manage messages and allowance/access requests.

## Purpose

Extract inbox management functionality from the Planet Hall viewer into a reusable cell type. Planet owners can add this cell to their workspace to:

- View incoming messages and reply to them
- View incoming allowance/access requests
- Approve or reject pending requests

## Actions

| Action | HTTP | Description |
|--------|------|-------------|
| `list_messages` | `GET /api/inbox/messages` | List received messages |
| `list_requests` | `GET /api/inbox/requests?direction=received` | List received requests |
| `approve_request` | `PUT /api/inbox/requests/{id}/status` | Approve a pending request |
| `reject_request` | `PUT /api/inbox/requests/{id}/status` | Reject a pending request |
| `reply_to_message` | `POST /api/inbox/messages` | Reply to a message |

## API Dependencies

All endpoints are provided by the existing `backend/app/routers/inbox_router.py`. No new endpoints were created.

- `GET /api/inbox/messages` — via CentralHub proxy
- `GET /api/inbox/requests?direction=received` — filters by `target_user_id`
- `PUT /api/inbox/requests/{id}/status` — validates ownership + state machine
- `POST /api/inbox/messages` — creates message via CentralHub proxy

## Architecture

- **InboxCell.ts**: BaseCell implementation with 5 actions via `apiFetch`
- **useInboxCell.ts**: Composable encapsulating cell execution with reactive state
- **View.vue**: Vue component with Messages/Requests tabs following the **Buffer Local Pattern** (REACTIVITY_ISOLATION.md)

## Directory Structure

```
cell_types/inbox-cell/
├── type.json                          → Symlink to ../../notebook_item_types/inbox-cell.json
├── frontend/
│   ├── InboxCell.ts                   → BaseCell implementation
│   ├── View.vue                       → Vue component with tabs
│   ├── composables/
│   │   └── useInboxCell.ts            → Reactive composable
│   └── tests/
│       └── InboxCell.spec.ts          → Unit tests (≥90% coverage)
└── docs/
    └── README.md                      → This file
```
