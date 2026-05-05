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
- **Global Lobby** — a shared default room accessible without any configuration.
- **Dynamic Rooms** — isolated named rooms scoped by `roomName`.

The cell is intentionally ephemeral in v1: history is stored in Redis with a 24-hour TTL
and is not persisted to a relational database.

---

## Salas Dinâmicas

Por padrão, a célula conecta ao **Lobby Global** (`global-planet-lobby`),
onde todos os usuários veem o mesmo chat.

### Criar uma Sala Específica

Para isolar mensagens em uma sala temática, defina `roomName` em `initial_data`:

```json
{
  "initial_data": {
    "roomName": "dev-reuniao"
  }
}
```

Resultado: Mensagens em `dev-reuniao` não aparecem em `global-planet-lobby` e vice-versa.

### Trocar de Sala em Runtime

Use o **Room Switcher** (input no header da célula):

1. Digite o nome da sala
2. Pressione Enter ou clique **Join**
3. O histórico da sala anterior é preservado no Redis (TTL 24 h)
4. O WebSocket reconecta automaticamente no novo canal

### Parâmetros

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `roomName` | `string \| null` | `null` | Nome da sala. `null` = Lobby Global (`global-planet-lobby`) |
| `partyId` | `string \| null` | `null` | **Deprecated** — use `roomName`. Ainda funciona como fallback |
| `maxMessages` | `integer` | `200` | Limite de mensagens mantidas no histórico local |

### Como o Isolamento Funciona

```
Sem parâmetros:
  resolveRoomId() → 'global-planet-lobby'
  channelContextId → 'planet-chat:global-planet-lobby'
  WSS: /wss/events?channel=planet-chat:global-planet-lobby

Com roomName = "dev-reuniao":
  channelContextId → 'planet-chat:dev-reuniao'
  Redis channel   → planet-chat:dev-reuniao   ← isolamento completo
```

**Segurança**: `roomName` é validado contra `^[\w:._-]{1,256}$` no backend antes de ser
usado como chave Redis.  Nomes com caracteres inválidos são rejeitados com erro.

---

## How Rooms Map to Channels

The `roomId` (bare room name, e.g. `global-planet-lobby`) maps to a Redis channel by
prepending the `planet-chat:` prefix:

```
WebSocket channel:  /wss/events?channel=planet-chat:{roomId}
Redis channel:      planet-chat:{roomId}
Redis snapshot key: planet-chat:snapshot:{roomId}
```

**Isolation guarantee**: two cells with different `roomId` values are completely
independent — messages for `room-A` are never delivered to a client subscribed to `room-B`.

### Safe characters

`roomId` must match `^[\w:._-]{1,256}$` — alphanumeric characters, colons, dots,
underscores, and hyphens.  The backend rejects any roomId that does not conform.

---

## Conflict Resolution Strategy

### `'append'` — used for `messages`

The message history is **append-only**.  Each message has a unique composite ID
(`"{timestamp}-{senderId}"`) and a timestamp.  JSON Patch operations always use
`{ op: "add", path: "/-" }` (append to end of array — path is relative to the array
branch received by `applySimplePatch`).

When two users send messages simultaneously:

```
User A @ t=100: PUBLISH planet-chat:X { patch: [{ op: "add", path: "/-", value: msgA }] }
Agent @ t=101:  PUBLISH planet-chat:X { patch: [{ op: "add", path: "/-", value: msgB }] }

Result: messages = [...existing, msgA, msgB]   ← both preserved
```

### `'lww'` — Last-Write-Wins (available for other branches)

For scalar state (e.g., `typing` indicators, presence), `useDistributedState` can be
configured with `conflictStrategy: 'lww'`.  The message with the highest `timestamp`
wins.  Simultaneous writes result in one value being silently dropped — acceptable for
ephemeral indicators.

---

## Integration with `useDistributedState`

`View.vue` uses the shared `useDistributedState` composable with a reactive
`ComputedRef<string>` so that room switches trigger automatic WebSocket reconnection:

```typescript
import { computed } from 'vue'
import { useDistributedState } from '@/composables/useDistributedState'

// channelContextId updates reactively when currentRoomId changes
const channelContextId = computed(() => `planet-chat:${currentRoomId.value}`)

const { isConnected, connectionError } = useDistributedState({
  contextId: channelContextId,          // ComputedRef<string> — auto-reconnects on change
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
| `contextId` ref changes | Disconnects old WS → connects new WS (room switch) |
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
| `send_message` | `contextId` (roomId), `message`, `senderId?`, `timestamp?` | `GET` snapshot → `SET` snapshot → `PUBLISH` patch |
| `snapshot_request` | `contextId` (roomId), `senderId?` | `GET` snapshot → `PUBLISH` snapshot |

> **Note**: `contextId` in the POST body is the **bare room name** (e.g. `global-planet-lobby`),
> not the prefixed channel name.  The backend adds the `planet-chat:` prefix internally.

---

## File Index

```
planet-chat-cell/
├── type.json                         # Cell type manifest
├── backend/
│   ├── scripts/main.py               # Redis PUBLISH handler
│   └── tests/test_main.py            # Backend unit tests (14 tests)
├── frontend/
│   ├── PlanetChatCell.ts             # BaseCell implementation (MANDATORY)
│   ├── View.vue                      # UI with Buffer Local Pattern + useDistributedState
│   ├── composables/
│   │   └── usePlanetChat.ts          # User-facing send/receive actions
│   ├── stores/
│   │   └── planetChat.ts             # Pinia store (messages, typing, currentRoom)
│   └── tests/
│       └── PlanetChatCell.spec.ts    # Frontend unit tests
└── docs/
    └── README.md                     # This file
```

---

## Security Notes

- WebSocket authentication is performed via the `sessionId` HttpOnly cookie **before**
  the HTTP 101 upgrade is accepted.  An invalid session receives `WS_1008_POLICY_VIOLATION`.
- The `roomId`/`contextId` provides **logical** isolation, not cryptographic.  A user with a
  valid session can subscribe to any channel by guessing the `roomId`.  For sensitive chats,
  consider `roomId = hash(partyId + secret)` (planned for v2).
- User input (`message` text, `roomName`) is JSON-serialised and never executed.

---

## Technical Debt & Future Work

| Item | Priority |
|------|----------|
| Database persistence (PostgreSQL) | Medium |
| End-to-end message encryption | Low |
| CRDT / Operational Transformation for collaborative editing | Low |
| User presence indicators (who's online) | Medium |
| Expose `onConnected` callback in `useDistributedState` to eliminate snapshot race on room switch | Low |
| Message reactions / threads | Low |
