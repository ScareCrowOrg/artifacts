# Party Cell — Backend Script

Backend execution script for the `party-cell` cell type.

## Discovery

The script is discovered by **path convention** by `cells_router.py`
(`POST /api/v1/cells/execute-ephemeral`):

```
artifacts/canonical/cell_types/party-cell/backend/scripts/main.py
```

It must export `execute_cell(cell_data, user_id=None)`.

## Actions

| Action | Purpose |
|--------|---------|
| `join_room` | Upsert the caller into the room presence snapshot + publish it |
| `leave_room` | Remove the caller from the room presence snapshot + publish it |
| `mute_toggle` | Flip the caller's `isMuted` flag + publish |
| `tracks_update` | Update the caller's published `tracks` (e.g. screen share) |
| `snapshot_request` | Publish the current participant snapshot to the channel |

## Redis Layout

- **Channel**: `calls:room:{roomId}` — must match the `usePartyCalls`
  `useDistributedState` contextId (`calls:room:{roomId}`).
- **Snapshot**: `calls:presence:{roomId}` — JSON array of participants
  (TTL 24h).

All actions publish a **snapshot** envelope (`type: "snapshot"`) so every
client's `useDistributedState` replaces its `participants` branch with the
authoritative list — no incremental-patch races, no LWW drops. The script is
the single source of truth for room presence.

## Sync to Runner (Local)

The backend container mounts `~/.scareverse/{tenant}/artifacts/canonical`
at `/app/artifacts/canonical`. Run the `/sync-artifacts` skill (robocopy) to
copy this script into the tenant directory — exactly like `planet-chat-cell`.

## Tests

```bash
cd artifacts/canonical/cell_types/party-cell/backend
python -m pytest tests/ -v
```
