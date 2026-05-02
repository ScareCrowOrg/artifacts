# Planet Chat Cell

Real-time multi-user chat cell powered by Redis Pub/Sub and WebSocket.
Multiple users in the same *party* see messages instantly (< 100 ms delivery).

---

## Purpose

`planet-chat-cell` is the first communication cell in the ScareVerse ecosystem.
It enables:

- **Real-time messaging** between human users and/or AI agents in a shared notebook party.
- **Distributed state synchronisation** — every connected client applies the same JSON Patch,
  so no browser needs to poll the server.
- **Append-only conflict resolution** — two users writing simultaneously keep *both* messages.

The cell is intentionally ephemeral in v1: history is stored in Redis with a 24-hour TTL
and is not persisted to a relational database.

---

## How `contextId` Works

The `contextId` is the string appended to the Redis channel name:

```
WebSocket channel:  /wss/events?channel=planet-chat:{contextId}
Redis channel:      planet-chat:{contextId}
Redis snapshot key: planet-chat:snapshot:{contextId}
```

**Isolation guarantee**: two cells with different `contextId` values are completely
independent — messages for `ctx-A` are never delivered to a client subscribed to `ctx-B`.

`contextId` defaults to the cell instance's unique ID when `partyId` is not supplied.
To share a chat room between multiple cells (e.g., a party of agents), pass the same
`partyId` to every `planet-chat-cell` instance.

### Safe characters

`contextId` must match `^[\w:._-]{1,256}$` — alphanumeric characters, colons, dots,
underscores, and hyphens.  The backend rejects any contextId that does not conform.

---

## Conflict Resolution Strategy

### `'append'` — used for `messages`

The message history is **append-only**.  Each message has a unique composite ID
(`"{timestamp}-{senderId}"`) and a timestamp.  JSON Patch operations always use
`{ op: "add", path: "/messages/-" }` (append to end of array).

When two users send messages simultaneously:

```
User A @ t=100: PUBLISH planet-chat:X { patch: [{ op: "add", path: "/messages/-", value: msgA }] }
Agent @ t=101:  PUBLISH planet-chat:X { patch: [{ op: "add", path: "/messages/-", value: msgB }] }

Result: messages = [...existing, msgA, msgB]   ← both preserved
```

### `'lww'` — Last-Write-Wins (available for other branches)

For scalar state (e.g., `typing` indicators, presence), `useDistributedState` can be
configured with `conflictStrategy: 'lww'`.  The message with the highest `timestamp`
wins.  Simultaneous writes result in one value being silently dropped — acceptable for
ephemeral indicators.

---

## Integration with `useDistributedState`

`View.vue` uses the shared `useDistributedState` composable:

```typescript
import { useDistributedState } from '@/composables/useDistributedState'

const { isConnected, connectionError } = useDistributedState({
  contextId: `planet-chat:${partyId}`,
  store: usePlanetChatStore() as unknown as Record<string, unknown>,
  branch: 'messages',
  conflictStrategy: 'append',
})
```

### What the composable does

| Event | Action |
|-------|--------|
| WebSocket opens | Sends `snapshot_request` → server publishes current state |
| Receives `snapshot` | Replaces `store.messages` with `payload.state` |
| Receives `patch` | Applies JSON Patch operations to `store.messages` |
| Local `store.messages` changes | Diffs against last-known-remote and sends patch |
| Component unmounts | Closes WebSocket, cancels watchers |

---

## Backend — `main.py`

The backend script is loaded dynamically by `cells_router.py` when the
`cell_type = "planet-chat-cell"`.  It exposes:

```python
async def execute_cell(cell_data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]
```

### Actions

| Action | Input fields | Redis operations |
|--------|-------------|-----------------|
| `send_message` | `contextId`, `message`, `senderId?`, `timestamp?` | `GET` snapshot → `SET` snapshot → `PUBLISH` patch |
| `snapshot_request` | `contextId`, `senderId?` | `GET` snapshot → `PUBLISH` snapshot |

---

## File Index

```
planet-chat-cell/
├── type.json                         # Symlink → ../../notebook_item_types/planet-chat-cell.json
├── backend/
│   ├── scripts/main.py               # Redis PUBLISH handler
│   └── tests/test_main.py            # Backend unit tests
├── frontend/
│   ├── PlanetChatCell.ts             # BaseCell implementation (MANDATORY)
│   ├── View.vue                      # UI with Buffer Local Pattern + useDistributedState
│   ├── composables/
│   │   └── usePlanetChat.ts          # User-facing send/receive actions
│   ├── stores/
│   │   └── planetChat.ts             # Pinia store (messages, typing, partyId)
│   └── tests/
│       └── PlanetChatCell.spec.ts    # Frontend unit tests
└── docs/
    └── README.md                     # This file
```

---

## Security Notes

- WebSocket authentication is performed via the `sessionId` HttpOnly cookie **before**
  the HTTP 101 upgrade is accepted.  An invalid session receives `WS_1008_POLICY_VIOLATION`.
- The `contextId` provides **logical** isolation, not cryptographic.  A user with a valid
  session can subscribe to any channel by guessing the `contextId`.  For sensitive chats,
  consider `contextId = hash(partyId + secret)` (planned for v2).
- User input (`message` text) is JSON-serialised and never executed.

---

## Technical Debt & Future Work

| Item | Priority |
|------|----------|
| Database persistence (PostgreSQL) | Medium |
| End-to-end message encryption | Low |
| CRDT / Operational Transformation for collaborative editing | Low |
| User presence indicators (who's online) | Medium |
| Multiple concurrent channels per cell | Low |
| Message reactions / threads | Low |
