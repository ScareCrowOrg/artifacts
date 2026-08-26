"""
puyo-party-cell — Backend Script (server-authoritative Puyo Puyo 1v1).

Executed by ``cells_router`` via ``POST /api/v1/cells/execute-ephemeral``.
Exports ``execute_cell(cell_data, user_id=None)``.  Server-authoritative
competitive Puyo: the backend issues the deterministic ``seed``, arbitrates
garbage and the winner, and is the ONLY writer to the game channel
``puyo:game:{roomId}`` (the WSS router is forward-only — the client is never
read on that endpoint).  Players join the room presence via party-cell's
``calls:presence:{roomId}`` contract (``usePartyCalls``); this script reads the
roster from there (never writes presence).

Redis layout
------------
- Channel:      ``puyo:game:{roomId}``           — WSS pub/sub; MUST match the
  frontend ``usePuyoRealtime`` contextId ``puyo:game:{roomId}``.
- Snapshot:     ``puyo:game:{roomId}:snapshot``  — JSON game state (TTL 24h).
- Roster:       ``calls:presence:{roomId}``      — party-cell presence
  (read-only here; written by usePartyCalls / party-cell backend).
- Lock:         ``puyo:lock:{roomId}``           — per-room lock (3s TTL) that
  serializes read-modify-write on state-mutating actions.

State shape (persisted snapshot)
-------------------------------
{
  "status": "waiting" | "running" | "game_over",
  "seed": int | None,          # deterministic piece-sequence seed
  "round": int,
  "scores": {pid: int},        # in-game points reported via piece_locked
  "readyFlags": {pid: bool},
  "garbagePending": {pid: int},# garbage units pending delivery (arbitrated)
  "grids": {pid: [72 ints]},   # compact 6x12 grids via piece_locked
  "gameOver": {"winnerId": str, "reason": str} | None
}

Security (OWASP): ``_caller_id`` prefers the authenticated ``user_id`` over any
client-supplied ``participantId`` (A07); state-mutating actions run under the
per-room lock to serialize read-modify-write (A04); ``piece_locked`` /
``submit_garbage`` payloads are sanitized (grid shape + amount bounds).  Full
server-side board simulation (anti-cheat) is explicitly out of scope for the
MVP — the backend arbitrates garbage/winner from client reports but never
trusts grid bytes for simulation.
"""

import json
import logging
import re
import secrets
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

SNAPSHOT_TTL_SECONDS = 86_400  # 24 hours
LOCK_TTL_MS = 3_000
BOARD_WIDTH = 6
BOARD_HEIGHT = 12
GRID_SIZE = BOARD_WIDTH * BOARD_HEIGHT  # 72
MAX_GARBAGE = 99
_SAFE_ROOM_ID_RE = re.compile(r"^[\w:._-]{1,256}$")


def _now_ms() -> int:
    return int(time.time() * 1000)


# ── Key / channel helpers ────────────────────────────────────────────────────


def _channel(room_id: str) -> str:
    return f"puyo:game:{room_id}"


def _snapshot_key(room_id: str) -> str:
    return f"puyo:game:{room_id}:snapshot"


def _presence_key(room_id: str) -> str:
    return f"calls:presence:{room_id}"


def _lock_key(room_id: str) -> str:
    return f"puyo:lock:{room_id}"


# ── Redis helpers ────────────────────────────────────────────────────────────


def _get_async_redis_client():
    """Return an async Redis client using the project-wide L1 config."""
    import redis.asyncio as aioredis
    from backend.app.config.database import (
        REDIS_L1_DB,
        REDIS_L1_HOST,
        REDIS_L1_PASSWORD,
        REDIS_L1_PORT,
    )

    kwargs: Dict[str, Any] = {
        "host": REDIS_L1_HOST,
        "port": REDIS_L1_PORT,
        "db": REDIS_L1_DB,
        "decode_responses": True,
        "socket_connect_timeout": 5,
    }
    if REDIS_L1_PASSWORD:
        kwargs["password"] = REDIS_L1_PASSWORD
    return aioredis.Redis(**kwargs)


async def _redis_get_json(key: str, default: Any) -> Any:
    client = await _get_async_redis_client()
    try:
        raw = await client.get(key)
        return default if raw is None else json.loads(raw)
    except Exception as exc:
        logger.warning("[puyo] Failed to load %s: %s", key, exc)
        return default
    finally:
        await client.aclose()


async def _redis_set_json(key: str, value: Any) -> None:
    client = await _get_async_redis_client()
    try:
        await client.set(key, json.dumps(value), ex=SNAPSHOT_TTL_SECONDS)
    except Exception as exc:
        logger.warning("[puyo] Failed to save %s: %s", key, exc)
    finally:
        await client.aclose()


async def _publish(channel: str, envelope: Dict[str, Any]) -> None:
    client = await _get_async_redis_client()
    try:
        await client.publish(channel, json.dumps(envelope))
    except Exception as exc:
        logger.warning("[puyo] Failed to publish to %s: %s", channel, exc)
    finally:
        await client.aclose()


def _snapshot_envelope(channel: str, state: Any, sender_id: str) -> Dict[str, Any]:
    return {
        "type": "snapshot",
        "contextId": channel,
        "senderId": sender_id,
        "timestamp": _now_ms(),
        "payload": {"state": state},
    }


# ── Per-room lock (serializes read-modify-write — OWASP A04) ─────────────────


async def _acquire_room_lock(room_id: str) -> bool:
    client = await _get_async_redis_client()
    try:
        return bool(await client.set(_lock_key(room_id), "1", nx=True, px=LOCK_TTL_MS))
    except Exception as exc:
        # Fail-open: Redis is required for the game anyway; never block on lock.
        logger.warning("[puyo] Lock acquire failed for %s: %s", room_id, exc)
        return True
    finally:
        await client.aclose()


async def _release_room_lock(room_id: str) -> None:
    client = await _get_async_redis_client()
    try:
        await client.delete(_lock_key(room_id))
    except Exception as exc:
        logger.warning("[puyo] Lock release failed for %s: %s", room_id, exc)
    finally:
        await client.aclose()


# ── Validation & identity helpers ────────────────────────────────────────────


def _require_room(cell_data: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Return ``(room_id, error)`` — error is None when the room is safe."""
    room_id: str = str(cell_data.get("roomId") or "").strip()
    if not room_id:
        return "", "roomId is required"
    if not _SAFE_ROOM_ID_RE.match(room_id):
        return "", "roomId contains invalid characters"
    return room_id, None


def _caller_id(cell_data: Dict[str, Any], user_id: Optional[str]) -> str:
    """Authoritative caller identity — the authenticated ``user_id`` wins."""
    return str(user_id or cell_data.get("participantId") or "unknown")


def _valid_grid(grid: Any) -> bool:
    return (
        isinstance(grid, list)
        and len(grid) == GRID_SIZE
        and all(isinstance(v, int) and 0 <= v <= 5 for v in grid)
    )


def _sanitize_amount(value: Any) -> int:
    """Clamp a garbage amount to a sane range; 0 when invalid/absent."""
    if isinstance(value, bool):
        return 0
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(amount, MAX_GARBAGE))


def _generate_seed() -> int:
    """32-bit seed for the deterministic piece queue (lockstep)."""
    return secrets.randbits(32)


# ── Game state helpers ───────────────────────────────────────────────────────


def _empty_state() -> Dict[str, Any]:
    return {
        "status": "waiting",
        "seed": None,
        "round": 0,
        "scores": {},
        "readyFlags": {},
        "garbagePending": {},
        "grids": {},
        "gameOver": None,
    }


async def _load_state(room_id: str) -> Dict[str, Any]:
    state = await _redis_get_json(_snapshot_key(room_id), None)
    return state if isinstance(state, dict) else _empty_state()


async def _save_state(room_id: str, state: Dict[str, Any]) -> None:
    await _redis_set_json(_snapshot_key(room_id), state)


async def _publish_snapshot(room_id: str, state: Dict[str, Any], sender_id: str) -> None:
    await _publish(_channel(room_id), _snapshot_envelope(_channel(room_id), state, sender_id))


async def _roster(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Players for this room, deduped by participantId, in priority order:

    1. Party presence (``calls:presence:{roomId}`` — party-cell contract).
    2. Client-supplied ``participants`` (fallback when presence is not yet
       populated, e.g. Cloudflare provisioning still in flight).
    3. ``readyFlags`` keys from the game state — ONLY when neither presence nor
       participants produced any player (pure fallback so a match can still
       start without voice presence).  Never re-injected when a real roster
       exists: a player who left keeps a stale ``ready`` flag and would
       otherwise persist as a ghost into the next match.

    Names resolve from presence/participants; ready-only players fall back to
    their participantId as the display name.
    """
    seen: Dict[str, str] = {}
    presence = await _redis_get_json(_presence_key(room_id), [])
    if isinstance(presence, list):
        for entry in presence:
            pid = str(entry.get("participantId") or "").strip()
            if pid and pid not in seen:
                seen[pid] = str(entry.get("displayName") or pid)
    for entry in cell_data.get("participants") or []:
        pid = str(entry.get("participantId") or "").strip()
        if pid and pid not in seen:
            seen[pid] = str(entry.get("displayName") or pid)
    if not seen:
        for pid in (state.get("readyFlags") or {}):
            if pid:
                seen[pid] = pid
    return [{"participantId": pid, "displayName": name} for pid, name in seen.items()]


def _match_players(players: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """The 1v1 match always runs between the FIRST TWO rostered players; any
    extra players in the room are spectators (voice/presence only) and never
    participate in scores/garbage/winner arbitration."""
    return players[:2]


async def _start_match(
    room_id: str,
    state: Dict[str, Any],
    players: List[Dict[str, str]],
    sender_id: str,
) -> Dict[str, Any]:
    """Transition the room to ``running`` with a fresh deterministic seed.

    The match is capped to 2 players (``_match_players``) so a 3+ player room
    never produces a malformed 1v1 (arbitrary ``others[0]`` winner / target).
    """
    players = _match_players(players)
    pids = [p["participantId"] for p in players]
    state.update({
        "status": "running",
        "seed": _generate_seed(),
        "round": int(state.get("round") or 0) + 1,
        "scores": {pid: 0 for pid in pids},
        "readyFlags": {pid: True for pid in pids},
        "garbagePending": {pid: 0 for pid in pids},
        "grids": {},
        "gameOver": None,
    })
    await _save_state(room_id, state)
    await _publish_snapshot(room_id, state, sender_id)
    logger.info("[puyo] start match room=%s seed=%s players=%d", room_id, state["seed"], len(pids))
    return {
        "success": True,
        "output": {"status": "running", "seed": state["seed"], "players": players},
    }


# ── Action decorator: room + lock (A04) ──────────────────────────────────────


def _action(*, locked: bool = False) -> Callable:
    """Validate roomId and optionally run the handler under the per-room lock."""

    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
            room_id, err = _require_room(cell_data)
            if err:
                return {"success": False, "output": {}, "error": err}
            if locked and not await _acquire_room_lock(room_id):
                return {"success": False, "output": {}, "error": "game is busy, try again"}
            try:
                state = await _load_state(room_id)
                return await fn(room_id, state, cell_data, user_id)
            finally:
                if locked:
                    await _release_room_lock(room_id)

        return wrapper

    return deco


# ── Action handlers ──────────────────────────────────────────────────────────


@_action(locked=True)
async def _handle_ready(
    room_id: str,
    state: Dict[str, Any],
    cell_data: Dict[str, Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """Mark the caller ready; auto-start with the first two ready players."""
    caller = _caller_id(cell_data, user_id)
    ready = dict(state.get("readyFlags") or {})
    ready[caller] = True
    state["readyFlags"] = ready
    # Roster AFTER marking ready so the caller is included via readyFlags.
    players = await _roster(room_id, state, cell_data)

    ready_players = [p for p in players if ready.get(p["participantId"])]
    if state.get("status") != "running" and len(ready_players) >= 2:
        await _save_state(room_id, state)
        return await _start_match(room_id, state, ready_players, caller)

    await _save_state(room_id, state)
    await _publish_snapshot(room_id, state, caller)
    return {
        "success": True,
        "output": {"status": state["status"], "readyFlags": ready, "participants": players},
    }


@_action(locked=True)
async def _handle_start_game(
    room_id: str,
    state: Dict[str, Any],
    cell_data: Dict[str, Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """Validate ≥2 players and start the match (explicit / re-match).

    The lobby uses ``ready`` (which auto-starts), so the ready gate here only
    applies to a fresh ``waiting`` state; a ``game_over`` state is a re-match
    and starts directly (the players just finished a match together).  In a 3+
    player room the match runs between the first two ready players (or the
    first two of the roster on a re-match) — extra players are spectators.
    """
    if state.get("status") == "running":
        return {"success": False, "output": {}, "error": "game already running"}
    caller = _caller_id(cell_data, user_id)
    players = await _roster(room_id, state, cell_data)
    pids = [p["participantId"] for p in players]
    if len(pids) < 2:
        return {"success": False, "output": {}, "error": "at least 2 players are required to start"}
    ready = dict(state.get("readyFlags") or {})
    if state.get("status") != "game_over":
        ready_players = [p for p in players if ready.get(p["participantId"])]
        if len(ready_players) < 2:
            return {"success": False, "output": {}, "error": "not all players are ready yet"}
        match = ready_players
    else:
        match = players
    state["readyFlags"] = ready
    return await _start_match(room_id, state, match, caller)


@_action(locked=True)
async def _handle_submit_garbage(
    room_id: str,
    state: Dict[str, Any],
    cell_data: Dict[str, Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """Accumulate a garbage attack on a target (sanitized amount).

    Both the caller and the target must be participants of the RUNNING match
    (from ``state.scores``, the authoritative 2-player set) — an outsider with
    the roomId cannot dump garbage or force a target (A01).
    """
    if state.get("status") != "running":
        return {"success": False, "output": {}, "error": "game is not running"}
    caller = _caller_id(cell_data, user_id)
    match_pids = list((state.get("scores") or {}).keys())
    if caller not in match_pids:
        return {"success": False, "output": {}, "error": "only match players can submit garbage"}
    amount = _sanitize_amount(cell_data.get("amount"))
    if amount <= 0:
        return {"success": False, "output": {}, "error": "amount must be a positive integer"}

    target = str(cell_data.get("targetId") or "").strip()
    if not target:
        # 1v1: the target is the opponent.
        others = [pid for pid in match_pids if pid != caller]
        target = others[0] if others else ""
    if not target or target not in match_pids or target == caller:
        return {"success": False, "output": {}, "error": "target must be a valid opponent"}

    pending = dict(state.get("garbagePending") or {})
    pending[target] = min(int(pending.get(target, 0)) + amount, MAX_GARBAGE)
    state["garbagePending"] = pending
    await _save_state(room_id, state)
    await _publish_snapshot(room_id, state, caller)
    return {"success": True, "output": {"garbagePending": pending, "target": target, "amount": amount}}


@_action(locked=True)
async def _handle_piece_locked(
    room_id: str,
    state: Dict[str, Any],
    cell_data: Dict[str, Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """Record the caller's compact grid (renders the opponent's board)."""
    if state.get("status") != "running":
        return {"success": False, "output": {}, "error": "game is not running"}
    caller = _caller_id(cell_data, user_id)
    match_pids = list((state.get("scores") or {}).keys())
    if caller not in match_pids:
        return {"success": False, "output": {}, "error": "only match players can report a board"}
    grid = cell_data.get("grid")
    if not _valid_grid(grid):
        return {"success": False, "output": {}, "error": "grid must be a compact 6x12 array of cell ids (0-5)"}

    grids = dict(state.get("grids") or {})
    grids[caller] = grid
    state["grids"] = grids

    score = cell_data.get("score")
    if isinstance(score, int) and score >= 0:
        scores = dict(state.get("scores") or {})
        scores[caller] = max(int(scores.get(caller, 0)), score)
        state["scores"] = scores

    await _save_state(room_id, state)
    await _publish_snapshot(room_id, state, caller)
    return {"success": True, "output": {"grids": grids}}


@_action(locked=True)
async def _handle_game_over(
    room_id: str,
    state: Dict[str, Any],
    cell_data: Dict[str, Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """The caller's board topped out → the opponent wins (server-arbitrated).

    Only a participant of the RUNNING match can end it (from ``state.scores``,
    the authoritative 2-player set); an outsider with the roomId cannot force a
    winner (A01).  The winner is the OTHER match player — never an arbitrary
    ``others[0]`` from a drifted roster.
    """
    if state.get("status") != "running":
        return {"success": True, "output": {"gameOver": state.get("gameOver")}}
    caller = _caller_id(cell_data, user_id)
    match_pids = list((state.get("scores") or {}).keys())
    if caller not in match_pids:
        return {"success": False, "output": {}, "error": "only match players can end the game"}
    others = [pid for pid in match_pids if pid != caller]
    if not others:
        return {"success": False, "output": {}, "error": "cannot determine an opponent"}

    winner_id = others[0]
    state["status"] = "game_over"
    state["gameOver"] = {"winnerId": winner_id, "reason": str(cell_data.get("reason") or "top-out")}
    # Reset ready flags so a stale `ready` from a previous match never
    # auto-starts the next one (a fresh match needs fresh ready clicks).
    state["readyFlags"] = {pid: False for pid in match_pids}
    await _save_state(room_id, state)
    await _publish_snapshot(room_id, state, caller)
    logger.info("[puyo] game_over room=%s winner=%s reason=%s", room_id, winner_id, state["gameOver"]["reason"])
    return {"success": True, "output": {"gameOver": state["gameOver"]}}


@_action()
async def _handle_snapshot_request(
    room_id: str,
    state: Dict[str, Any],
    cell_data: Dict[str, Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """Re-publish the current snapshot AND return it in the HTTP body.

    The WSS router is forward-only, so a WS snapshot_request on connect is never
    answered and a snapshot published before this client's WS subscribed is
    lost.  The response body is the reliable hydration path (same lesson as
    party-game v2.3) — the View hydrates ``game`` + ``participantId`` from it.
    """
    sender = _caller_id(cell_data, user_id)
    players = await _roster(room_id, state, cell_data)
    await _publish_snapshot(room_id, state, sender)
    return {
        "success": True,
        "output": {
            "state": state,
            "participantId": sender,
            "participants": players,
        },
    }


# ── Entry point ──────────────────────────────────────────────────────────────


_HANDLERS: Dict[str, Any] = {
    "ready": _handle_ready,
    "start_game": _handle_start_game,
    "submit_garbage": _handle_submit_garbage,
    "piece_locked": _handle_piece_locked,
    "game_over": _handle_game_over,
    "snapshot_request": _handle_snapshot_request,
}


async def execute_cell(
    cell_data: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Entry point called by ``cells_router`` (execute-ephemeral)."""
    action: str = str(cell_data.get("action") or "").strip()
    logger.debug("[puyo] execute_cell action=%s user_id=%s", action, user_id)
    handler = _HANDLERS.get(action)
    if handler is None:
        return {
            "success": False,
            "output": {},
            "error": f"Unknown action: '{action}'. Supported: {', '.join(sorted(_HANDLERS))}",
        }
    return await handler(cell_data, user_id)


# ── CLI testing helper (dev-only — excluded from coverage) ───────────────────

if __name__ == "__main__":  # pragma: no cover
    import asyncio
    import sys

    test_payload = {"action": "snapshot_request", "roomId": "test-room"}

    if len(sys.argv) > 1:
        try:
            test_payload = json.loads(sys.argv[1])
        except json.JSONDecodeError as exc:
            print(f"Error parsing JSON argument: {exc}", file=sys.stderr)
            sys.exit(1)

    result = asyncio.run(execute_cell(test_payload, user_id="cli-user"))
    print(json.dumps(result, indent=2))
