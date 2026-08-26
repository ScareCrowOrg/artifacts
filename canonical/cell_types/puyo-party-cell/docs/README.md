# Puyo Party Cell

Real-time competitive **Puyo Puyo 1v1** (Canvas 2D) built on the existing realtime building
blocks — deterministic lockstep engine, server-authoritative sync and opt-in voice.

## Overview

Two players share a room, get a shared deterministic `seed` from the backend and simulate the
**same piece sequence** locally (lockstep, zero latency). Each player clears chains to send
garbage to the opponent (`submit_garbage`, server-arbitrated), the opponent's board renders from
the reported grid (`piece_locked`), and the match ends when a board tops out (`game_over`, backend
arbitrates the winner). Voice (opt-in — mic silent until the first click) comes from Cloudflare
Calls via `usePartyCalls`.

No new infrastructure: a single distributed state branch (`game`, lww) over Redis Pub/Sub
(`puyo:game:{roomId}`) + the existing `/wss/events` forward-only router + Cloudflare Calls.

## Architecture

```
Browser (View.vue)
├─ PuyoPartyCell.ts (BaseCell) → POST /api/v1/cells/execute-ephemeral  (WRITE path)
│     action: ready · start_game · submit_garbage · piece_locked · game_over · snapshot_request
├─ puyoStore (Pinia) — branch `game` (lww)  ← backend snapshot envelopes (seed/scores/garbage)
│     usePuyoRealtime: /wss/events?channel=puyo:game:{roomId}  (READ-only forward)
├─ usePartyCalls → presence + opt-in voice (partyStore.participants, calls:room:{roomId})
├─ engine/  PuyoBoard · PuyoGarbage · PuyoRNG  (local sim, zero latency, deterministic)
└─ <canvas> two 2D boards (self + remote from game.grids) + HUD

Backend: puyo-party-cell/backend/scripts/main.py (server-authoritative)
├─ execute_cell(action, ...) — ready (auto-start) / start_game (seed) / submit_garbage /
│     piece_locked (compact grid) / snapshot_request (hydration) / game_over (winner)
├─ publishes snapshot envelopes to Redis channel puyo:game:{roomId}
└─ reads the roster from calls:presence:{roomId} (party-cell contract)
```

> ⚠️ **WSS forward-only** (`wss_pubsub_router.py:189`): the client is never read on `/wss/events`.
> EVERY write goes through `execute-ephemeral → backend PUBLISH → WS forward`. `useDistributedState`
> is a receiver; the backend is the only writer to `puyo:game:{roomId}`.

## Redis Layout

| Channel / Key | Writer | Reader | Envelope |
|---|---|---|---|
| `puyo:game:{roomId}` | Backend (`main.py` PUBLISH) | All clients → `puyoStore.game` (lww) | `snapshot` |
| `puyo:game:{roomId}:snapshot` (TTL 24h) | Backend (SET) | Backend (load/persist) | JSON state |
| `calls:room:{roomId}` | party-cell backend (existing) | All clients → `partyStore.participants` | `snapshot` (presence) |
| `puyo:lock:{roomId}` (TTL 3s) | Backend (SET NX) | Backend (per-room mutex) | — |

## State Shape

```json
{
  "status": "waiting | running | game_over",
  "seed": 12345,
  "round": 1,
  "scores": { "user-1": 120, "user-2": 40 },
  "readyFlags": { "user-1": true, "user-2": true },
  "garbagePending": { "user-1": 0, "user-2": 6 },
  "grids": { "user-1": [0,0,...72], "user-2": [0,0,...72] },
  "gameOver": { "winnerId": "user-2", "reason": "top-out" }
}
```

## Actions

| Action | Purpose | Server validation |
|---|---|---|
| `ready` | Mark the caller ready; **auto-starts** when all rostered players are ready | roomId safe |
| `start_game` | Explicit start / re-match — issues the deterministic `seed` | ≥2 players; not already running; ready gate on `waiting` (re-match after `game_over` starts directly) |
| `submit_garbage` | Deliver a garbage attack (units) to a target | `1 ≤ amount ≤ 99`; target is a valid opponent |
| `piece_locked` | Report the caller's compact 6×12 grid + score | grid is exactly 72 cell ids `0..5` |
| `game_over` | The caller topped out → backend arbitrates the opponent as winner | running state; ≥2 players |
| `snapshot_request` | Re-publish + **return** state in the HTTP body (hydration) | roomId safe |

> **Hydration via HTTP body**: the WSS router is forward-only, so a snapshot published before a
> client's WS subscribed is lost. `View.vue` hydrates `game`, `participantId` and `participants`
> from the `snapshot_request` RESPONSE BODY (same lesson as party-game v2.3).

## Deterministic Engine

- `engine/PuyoRNG.ts` — mulberry32 PRNG; same seed → same piece sequence (lockstep).
- `engine/PuyoBoard.ts` — 6×12 grid, gravity, BFS ≥4, chain cascades (garbage cleared when
  adjacent to a chain), top-out detection, and a `PuyoSession` (board + piece + garbage queue).
- `engine/PuyoGarbage.ts` — 2 stones per garbage unit, classic chain-power table (capped at 45),
  and in-board garbage distribution with a **separate** RNG (never perturbs the piece queue).

## States

1. **Lobby** — roster from `partyStore.participants`; each player clicks **Ready**; auto-start when
   all are ready.
2. **Running** — local simulation driven by the shared seed; two canvases (self + opponent);
   HUD shows score, round and pending garbage.
3. **Game Over** — backend arbitrates the winner; **Play Again** issues a fresh seed.

## Integration

### Adding to a viewer
```typescript
import { usePuyoStore, usePuyoRealtime } from './store/puyoStore'
import { PuyoPartyCell } from './PuyoPartyCell'
```
The View is auto-discovered via `type.json` `default_refs`; translations are auto-loaded by
`useAutoLoadCellI18n` from `frontend/translations/{en,pt-BR}.json`.

### Required environment
- Redis L1 (existing) — game channel + snapshot key.
- Cloudflare Calls credentials in vault (opt-in voice; the game works without presence, roster
  falls back to ready flags / client-supplied participants).
- Browser with Canvas 2D + keyboard.

## Translations

- `en.json` — English
- `pt-BR.json` — Portuguese (Brazil)

## Security notes

- `_caller_id` prefers the authenticated `user_id` over client-supplied `participantId`.
- State-mutating actions run under a per-room Redis lock (`puyo:lock:{roomId}`, 3s TTL).
- Garbage amounts and grid payloads are sanitized/clamped. Full server-side board simulation
  (anti-cheat) is explicitly **out of scope for the MVP**.
