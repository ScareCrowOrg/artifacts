# Party Game Cell

## Overview

A real-time **drawing / guessing party game** (Gartic-like) where **AI participates**:
it picks the secret word, judges guesses and gives progressive hints.  Players join a
room, take turns as the drawer, the others guess, and the backend orchestrates rounds
and scoring **server-authoritatively**.

The cell is a **micro app composed from the existing realtime foundation** — no new
infrastructure:

| Building block | Role |
|----------------|------|
| `useDistributedState` | Syncs 3 branches (`game` lww · `strokes` append · `guesses` append) over Redis Pub/Sub |
| `partyStore` (`participants`) | Room roster — reuses the party presence contract |
| `party-cell` presence | `join_game`/`leave_game` write the same `calls:presence:` key + `calls:room:` channel |
| Backend `main.py` | Server-authoritative orchestrator (word/judge/hint + strokes/guesses) |

## How the game flows

1. Players join a room (presence via `calls:room:{roomId}`).
2. Any player with **2+ players** in the roster starts the game (`start_game`).
3. The backend picks a **drawer** (round-robin) and a **secret word** (LLM `ollama`
   with a **word-bank fallback** — offline/deterministic).
4. The drawer draws on the canvas; every committed stroke is appended to the `strokes`
   branch and rendered live by all players.
5. Guessers submit guesses; the backend **validates** (normalized exact/contains),
   **scores** (faster = more points) and publishes a **hint** after N wrong guesses.
6. `next_round` advances (revealing the previous word) or `end_game` finishes.

## Properties

### roomId (string | null)
- Room identifier for the game.  Scopes the game and its Redis channels
  (`game:room:{roomId}:*`).
- Default: `null` — the user enters a room name in the cell lobby.

## AI behaviour (server-side)

- **Word picker**: calls the Ollama `/api/generate` endpoint at the URL resolved by
  `_ollama_base_url()` — env `OLLAMA_BASE_URL` → `OLLAMA_HOST` → backend config
  (`ollama_base_url`) → loopback fallback; on ANY failure falls back to the curated
  word bank (`backend/scripts/word_bank.py`).
- **Judge**: `submit_guess` normalizes the guess (accents/case/punctuation stripped)
  and matches exact-or-phrase-contains the secret word (one-directional — a short
  guess that is a prefix of the word does not match).
- **Hints**: after every 3 wrong guesses (and on the drawer-only `hint` action), a
  progressive template hint is appended to the `guesses` feed.

## Security (OWASP A01/A07)

- The secret word **never appears in any published envelope** — it lives in Redis
  (`game:word:{roomId}`) and is returned **only to the drawer** via the authenticated
  `get_secret` action response.
- **Authorization**: destructive actions (`start_round`, `next_round`, `end_game`,
  `hint`, `append_stroke`, `clear_canvas`) are gated to the current drawer.
- **Identity**: the authenticated `user_id` is authoritative over any client-supplied
  `participantId` (not spoofable).
- **Concurrency**: state-mutating actions run under a per-room Redis lock
  (`game:lock:{roomId}`) to serialize read-modify-write.

## Actions (backend `execute_cell`)

`join_game` · `leave_game` · `start_game` · `start_round` · `next_round` · `end_game` ·
`get_secret` · `submit_guess` · `hint` · `append_stroke` · `clear_canvas` ·
`snapshot_request`.

## Files

```
party-game/
├── type.json                      # Cell type registration (category: game)
├── backend/
│   ├── scripts/main.py            # Server-authoritative game orchestrator
│   ├── scripts/word_bank.py       # Word bank + LLM fallback + hints
│   └── tests/test_main.py         # 100% line coverage (main + word_bank)
├── frontend/
│   ├── gameStore.ts               # Pinia store + useGameRealtime (3 branches + presence)
│   ├── canvas.ts                  # Pure drawing utilities (Buffer Local)
│   ├── PartyGameCell.ts           # BaseCell implementation
│   ├── View.vue                   # Lobby / round / canvas / guess feed / scoreboard
│   ├── translations/              # en.json + pt-BR.json
│   └── tests/                     # canvas.spec.ts + PartyGameCell.spec.ts (100%)
└── docs/README.md
```

## References

- Wireframe: `docs/official/wireframe/artifacts/cell_types/PARTY_GAME_FLOW_WIREFRAME.md`
- Foundation: `artifacts/shared/composables/useDistributedState.ts`,
  `artifacts/shared/stores/partyStore.ts`
- Issue: `docs/issues/party-game/ISSUE.md`
