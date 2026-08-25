"""
party-game — Backend Script (server-authoritative game orchestrator).

Executed by ``cells_router`` via ``POST /api/v1/cells/execute-ephemeral``.
Exports ``execute_cell(cell_data, user_id=None)``.  Gartic-like game where AI
picks the word, judges guesses and gives hints.  Composes the realtime
foundation: presence reuses ``party-cell``'s ``calls:presence:``/``calls:room:``
contract; the WSS router is forward-only, so the BACKEND is the only writer to
the game channels (``game:room:{roomId}:state|strokes|guesses``).  The secret
word is returned ONLY to the drawer via ``get_secret``.

Security (OWASP): ``_caller_id`` prefers the authenticated ``user_id`` over any
client-supplied ``participantId`` (A07); destructive actions are drawer-gated
via ``_action(drawer=True)`` (A01); state-mutating actions run under a per-room
Redis lock ``game:lock:{roomId}`` to serialize read-modify-write (A04).

Actions: join_game · leave_game · start_game · start_round · next_round ·
end_game · get_secret · submit_guess · hint · append_stroke · clear_canvas ·
snapshot_request.
"""

import json
import logging
import re
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

from word_bank import HINT_WRONG_COUNT, generate_hint, guess_matches, pick_word_with_llm

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

SNAPSHOT_TTL_SECONDS = 86_400  # 24 hours
_SAFE_ROOM_ID_RE = re.compile(r"^[\w:._-]{1,256}$")
CORRECT_POINTS = 100
POINTS_PER_WRONG = 10
MIN_POINTS = 10
LOCK_TTL_MS = 3_000


# ── Channel / key helpers ────────────────────────────────────────────────────


def _channel_state(room_id: str) -> str:
    return f"game:room:{room_id}:state"


def _channel_strokes(room_id: str) -> str:
    return f"game:room:{room_id}:strokes"


def _channel_guesses(room_id: str) -> str:
    return f"game:room:{room_id}:guesses"


def _key_state(room_id: str) -> str:
    return f"game:state:{room_id}"


def _key_strokes(room_id: str) -> str:
    return f"game:strokes:{room_id}"


def _key_guesses(room_id: str) -> str:
    return f"game:guesses:{room_id}"


def _key_word(room_id: str) -> str:
    return f"game:word:{room_id}"


def _presence_key(room_id: str) -> str:
    return f"calls:presence:{room_id}"


def _presence_channel(room_id: str) -> str:
    return f"calls:room:{room_id}"


def _lock_key(room_id: str) -> str:
    return f"game:lock:{room_id}"


def _now_ms() -> int:
    return int(time.time() * 1000)


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
        logger.warning("[party-game] Failed to load %s: %s", key, exc)
        return default
    finally:
        await client.aclose()


async def _redis_set_json(key: str, value: Any) -> None:
    client = await _get_async_redis_client()
    try:
        await client.set(key, json.dumps(value), ex=SNAPSHOT_TTL_SECONDS)
    except Exception as exc:
        logger.warning("[party-game] Failed to save %s: %s", key, exc)
    finally:
        await client.aclose()


async def _publish(channel: str, envelope: Dict[str, Any]) -> None:
    client = await _get_async_redis_client()
    try:
        await client.publish(channel, json.dumps(envelope))
    except Exception as exc:
        logger.warning("[party-game] Failed to publish to %s: %s", channel, exc)
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


def _patch_envelope(channel: str, branch: str, value: Any, sender_id: str) -> Dict[str, Any]:
    return {
        "type": "patch",
        "contextId": channel,
        "senderId": sender_id,
        "timestamp": _now_ms(),
        "payload": {
            "branch": branch,
            "operations": [{"op": "add", "path": "/-", "value": value}],
        },
    }


# ── Per-room lock (serializes read-modify-write — OWASP A04) ─────────────────


async def _acquire_room_lock(room_id: str) -> bool:
    client = await _get_async_redis_client()
    try:
        return bool(await client.set(_lock_key(room_id), "1", nx=True, px=LOCK_TTL_MS))
    except Exception as exc:
        # Fail-open: Redis is required for the game anyway; never block on lock.
        logger.warning("[party-game] Lock acquire failed for %s: %s", room_id, exc)
        return True
    finally:
        await client.aclose()


async def _release_room_lock(room_id: str) -> None:
    client = await _get_async_redis_client()
    try:
        await client.delete(_lock_key(room_id))
    except Exception as exc:
        logger.warning("[party-game] Lock release failed for %s: %s", room_id, exc)
    finally:
        await client.aclose()


# ── Shared validation & identity helpers ─────────────────────────────────────


def _require_room(cell_data: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Return ``(room_id, error)`` — error is None when the room is safe."""
    room_id: str = str(cell_data.get("roomId") or "").strip()
    if not room_id:
        return "", "roomId is required"
    if not _SAFE_ROOM_ID_RE.match(room_id):
        return "", "roomId contains invalid characters"
    return room_id, None


def _caller_id(cell_data: Dict[str, Any], user_id: Optional[str]) -> str:
    """Authoritative caller identity — the authenticated ``user_id`` wins.

    A client-supplied ``participantId`` is only a fallback (e.g. tests/CLI).
    This makes ``get_secret`` (and every drawer gate) non-spoofable (A07).
    """
    return str(user_id or cell_data.get("participantId") or "unknown")


def _is_drawer(state: Dict[str, Any], caller_id: str) -> bool:
    return bool(state.get("drawerId")) and str(state.get("drawerId")) == caller_id


def _display_name(state: Dict[str, Any], caller_id: str, cell_data: Dict[str, Any]) -> str:
    for p in state.get("players") or []:
        if p["participantId"] == caller_id:
            return p["displayName"]
    return str(cell_data.get("displayName") or caller_id)


# ── Game state helpers ───────────────────────────────────────────────────────


def _empty_game_state() -> Dict[str, Any]:
    return {
        "round": 0,
        "totalRounds": 0,
        "phase": "lobby",
        "drawerId": None,
        "drawerName": None,
        "category": None,
        "hintCount": 0,
        "wrongCount": 0,
        "scores": {},
        "roundWinners": [],
        "players": [],
    }


async def _load_state(room_id: str) -> Dict[str, Any]:
    state = await _redis_get_json(_key_state(room_id), None)
    return state if isinstance(state, dict) else _empty_game_state()


async def _load_list(key: str) -> List[Dict[str, Any]]:
    value = await _redis_get_json(key, [])
    return value if isinstance(value, list) else []


async def _load_players(room_id: str, cell_data: Dict[str, Any]) -> List[Dict[str, str]]:
    # Roster from party presence (deduped by participantId) or client fallback.
    presence = await _redis_get_json(_presence_key(room_id), [])
    if isinstance(presence, list) and presence:
        seen: Dict[str, str] = {}
        for entry in presence:
            pid = str(entry.get("participantId") or "").strip()
            if pid and pid not in seen:
                seen[pid] = str(entry.get("displayName") or pid)
        return [{"participantId": pid, "displayName": name} for pid, name in seen.items()]

    players: List[Dict[str, str]] = []
    seen_ids = set()
    for entry in cell_data.get("participants") or []:
        pid = str(entry.get("participantId") or "").strip()
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            players.append({"participantId": pid, "displayName": str(entry.get("displayName") or pid)})
    return players


async def _append_guess(room_id: str, msg: Dict[str, Any], sender_id: str) -> None:
    guesses = await _load_list(_key_guesses(room_id))
    guesses.append(msg)
    await _redis_set_json(_key_guesses(room_id), guesses)
    await _publish(_channel_guesses(room_id), _patch_envelope(_channel_guesses(room_id), "guesses", msg, sender_id))


def _sys_msg(msg_id: str, text: str) -> Dict[str, Any]:
    return {"id": msg_id, "userId": "system", "displayName": "System", "text": text, "type": "system"}


# ── Action decorator: room + authorization (A01) + lock (A04) ────────────────


def _action(*, drawer: bool = False, locked: bool = False) -> Callable:
    """Validate roomId; optionally gate to the drawer and run under the lock."""

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
                if drawer:
                    if not state.get("players"):
                        return {"success": False, "output": {}, "error": "start the game first"}
                    if not _is_drawer(state, _caller_id(cell_data, user_id)):
                        return {"success": False, "output": {}, "error": "only the drawer can do that"}
                return await fn(room_id, state, cell_data, user_id)
            finally:
                if locked:
                    await _release_room_lock(room_id)

        return wrapper

    return deco


# ── Round runner ─────────────────────────────────────────────────────────────


async def _run_next_round(room_id: str, state: Dict[str, Any], sender_id: str) -> Dict[str, Any]:
    players: List[Dict[str, str]] = state.get("players") or []
    if not players:
        return {"success": False, "output": {}, "error": "no players in the game"}

    next_round = int(state.get("round") or 0) + 1
    if next_round > int(state.get("totalRounds") or 0):
        return await _finish_game(room_id, state, sender_id)

    drawer = players[(next_round - 1) % len(players)]
    category, word = pick_word_with_llm()
    await _redis_set_json(_key_word(room_id), word)

    state.update({
        "round": next_round,
        "phase": "draw",
        "drawerId": drawer["participantId"],
        "drawerName": drawer["displayName"],
        "category": category,
        "hintCount": 0,
        "wrongCount": 0,
        "roundWinners": [],
    })
    await _redis_set_json(_key_state(room_id), state)
    await _publish(_channel_state(room_id), _snapshot_envelope(_channel_state(room_id), state, sender_id))
    await _redis_set_json(_key_strokes(room_id), [])
    await _publish(_channel_strokes(room_id), _snapshot_envelope(_channel_strokes(room_id), [], sender_id))
    await _append_guess(room_id, _sys_msg(
        f"sys-r{next_round}", f"Round {next_round}: {drawer['displayName']} is drawing ({category})!",
    ), sender_id)

    logger.info("[party-game] round %s room=%s drawer=%s", next_round, room_id, drawer["participantId"])
    return {
        "success": True,
        "output": {
            "round": next_round,
            "phase": "draw",
            "drawerId": drawer["participantId"],
            "drawerName": drawer["displayName"],
            "category": category,
            "players": players,
        },
    }


async def _finish_game(room_id: str, state: Dict[str, Any], sender_id: str) -> Dict[str, Any]:
    word = await _redis_get_json(_key_word(room_id), None)
    state.update({"phase": "finished", "drawerId": None, "drawerName": None})
    await _redis_set_json(_key_state(room_id), state)
    await _publish(_channel_state(room_id), _snapshot_envelope(_channel_state(room_id), state, sender_id))
    if word:
        await _append_guess(room_id, _sys_msg("sys-end", f"Game over! The last word was '{word}'. Final scores below."), sender_id)
    logger.info("[party-game] end_game room=%s", room_id)
    return {"success": True, "output": {"phase": "finished", "scores": state.get("scores", {})}}


# ── Action handlers ──────────────────────────────────────────────────────────


@_action(locked=True)
async def _handle_join_game(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    session_id = str(cell_data.get("sessionId") or "").strip()
    participant_id = _caller_id(cell_data, user_id)
    display_name = str(cell_data.get("displayName") or "")
    current_user = cell_data.get("_current_user")
    if not display_name and current_user is not None:
        display_name = str(getattr(current_user, "name", "") or "")
    display_name = display_name or participant_id

    participants = await _load_list(_presence_key(room_id))
    entry = {
        "participantId": participant_id,
        "sessionId": session_id or participant_id,
        "displayName": display_name,
        "tracks": cell_data.get("tracks") or [],
        "isMuted": bool(cell_data.get("isMuted", False)),
        "joinedAt": int(cell_data.get("joinedAt") or _now_ms()),
    }
    replaced = False
    for idx, existing in enumerate(participants):
        if str(existing.get("sessionId") or "") == entry["sessionId"]:
            participants[idx] = entry
            replaced = True
            break
    if not replaced:
        participants.append(entry)

    await _redis_set_json(_presence_key(room_id), participants)
    await _publish(_presence_channel(room_id), _snapshot_envelope(_presence_channel(room_id), participants, participant_id))
    return {
        "success": True,
        "output": {"participants": participants, "count": len(participants), "participantId": participant_id},
    }


@_action(locked=True)
async def _handle_leave_game(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    session_id = str(cell_data.get("sessionId") or "").strip()
    participant_id = _caller_id(cell_data, user_id)
    participants = await _load_list(_presence_key(room_id))
    if session_id:
        remaining = [p for p in participants if str(p.get("sessionId") or "") != session_id]
    else:
        remaining = [p for p in participants if str(p.get("participantId") or "") != participant_id]
    if len(remaining) != len(participants):
        await _redis_set_json(_presence_key(room_id), remaining)
        await _publish(_presence_channel(room_id), _snapshot_envelope(_presence_channel(room_id), remaining, participant_id))
        participants = remaining
    return {"success": True, "output": {"participants": participants, "count": len(participants)}}


@_action(locked=True)
async def _handle_start_game(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    players = await _load_players(room_id, cell_data)
    if len(players) < 2:
        return {"success": False, "output": {}, "error": "at least 2 players are required to start"}

    total_rounds = max(1, min(int(cell_data.get("totalRounds") or (len(players) * 2)), 20))
    new_state = _empty_game_state()
    new_state.update({
        "totalRounds": total_rounds,
        "scores": {p["participantId"]: 0 for p in players},
        "players": players,
    })
    await _redis_set_json(_key_state(room_id), new_state)
    await _redis_set_json(_key_guesses(room_id), [])
    await _publish(_channel_state(room_id), _snapshot_envelope(_channel_state(room_id), new_state, _caller_id(cell_data, user_id)))
    return await _run_next_round(room_id, new_state, _caller_id(cell_data, user_id))


@_action(drawer=True, locked=True)
async def _handle_start_round(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    return await _run_next_round(room_id, state, _caller_id(cell_data, user_id))


@_action(drawer=True, locked=True)
async def _handle_next_round(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    previous_word = await _redis_get_json(_key_word(room_id), None)
    if previous_word and state.get("round", 0) > 0:
        await _append_guess(room_id, _sys_msg(f"sys-reveal-{state['round']}", f"The word was '{previous_word}'!"), _caller_id(cell_data, user_id))
    return await _run_next_round(room_id, state, _caller_id(cell_data, user_id))


@_action(drawer=True, locked=True)
async def _handle_end_game(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    return await _finish_game(room_id, state, _caller_id(cell_data, user_id))


@_action(drawer=True)
async def _handle_get_secret(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    word = await _redis_get_json(_key_word(room_id), None)
    if word is None:
        return {"success": False, "output": {}, "error": "no active round"}
    return {"success": True, "output": {"secretWord": word, "round": state.get("round")}}


@_action(locked=True)
async def _handle_submit_guess(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    guess_text: str = str(cell_data.get("guess") or "").strip()
    if not guess_text:
        return {"success": False, "output": {}, "error": "guess is required"}

    if state.get("phase") not in ("draw", "guess", "reveal"):
        return {"success": False, "output": {}, "error": "no active round to guess"}

    word = await _redis_get_json(_key_word(room_id), None)
    if not word:
        return {"success": False, "output": {}, "error": "no secret word for this round"}

    caller_id = _caller_id(cell_data, user_id)
    if _is_drawer(state, caller_id):
        return {"success": True, "output": {"status": "drawer", "message": "the drawer does not guess"}}

    display_name = _display_name(state, caller_id, cell_data)
    scores = dict(state.get("scores") or {})
    wrong_count = int(state.get("wrongCount") or 0)
    hint_count = int(state.get("hintCount") or 0)
    winners = list(state.get("roundWinners") or [])

    if guess_matches(guess_text, word):
        if caller_id not in winners:
            points = max(MIN_POINTS, CORRECT_POINTS - wrong_count * POINTS_PER_WRONG)
            scores[caller_id] = int(scores.get(caller_id, 0)) + points
            winners.append(caller_id)
            await _append_guess(room_id, {
                "id": f"g-{_now_ms()}",
                "userId": caller_id,
                "displayName": display_name,
                "text": guess_text,
                "type": "guess",
                "isCorrect": True,
            }, caller_id)
            state.update({"scores": scores, "roundWinners": winners, "phase": "reveal"})
            await _redis_set_json(_key_state(room_id), state)
            await _publish(_channel_state(room_id), _snapshot_envelope(_channel_state(room_id), state, caller_id))
            return {"success": True, "output": {"correct": True, "points": points, "scores": scores}}
        return {"success": True, "output": {"correct": True, "already": True, "scores": scores}}

    wrong_count += 1
    await _append_guess(room_id, {
        "id": f"g-{_now_ms()}",
        "userId": caller_id,
        "displayName": display_name,
        "text": guess_text,
        "type": "guess",
        "isCorrect": False,
    }, caller_id)

    hint_text = None
    if wrong_count % HINT_WRONG_COUNT == 0:
        hint_count += 1
        hint_text = generate_hint(word, hint_count, state.get("category"))
        await _append_guess(room_id, {
            "id": f"h-{_now_ms()}",
            "userId": "system",
            "displayName": "System",
            "text": hint_text,
            "type": "hint",
        }, caller_id)

    # Only escalate draw → guess; never regress a resolved round (reveal).
    if state.get("phase") == "draw":
        state["phase"] = "guess"
    state.update({"wrongCount": wrong_count, "hintCount": hint_count, "scores": scores})
    await _redis_set_json(_key_state(room_id), state)
    await _publish(_channel_state(room_id), _snapshot_envelope(_channel_state(room_id), state, caller_id))
    return {"success": True, "output": {"correct": False, "hint": hint_text, "wrongCount": wrong_count}}


@_action(drawer=True, locked=True)
async def _handle_hint(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    word = await _redis_get_json(_key_word(room_id), None)
    if not word:
        return {"success": False, "output": {}, "error": "no active round"}

    hint_count = int(state.get("hintCount") or 0) + 1
    hint_text = generate_hint(word, hint_count, state.get("category"))
    state["hintCount"] = hint_count
    await _redis_set_json(_key_state(room_id), state)
    await _append_guess(room_id, {
        "id": f"h-{_now_ms()}",
        "userId": "system",
        "displayName": "System",
        "text": hint_text,
        "type": "hint",
    }, _caller_id(cell_data, user_id))
    await _publish(_channel_state(room_id), _snapshot_envelope(_channel_state(room_id), state, _caller_id(cell_data, user_id)))
    return {"success": True, "output": {"hint": hint_text, "hintCount": hint_count}}


@_action(drawer=True, locked=True)
async def _handle_append_stroke(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    stroke = cell_data.get("stroke")
    if not isinstance(stroke, dict):
        return {"success": False, "output": {}, "error": "stroke is required"}

    strokes = await _load_list(_key_strokes(room_id))
    stroke["id"] = stroke.get("id") or f"s-{_now_ms()}"
    strokes.append(stroke)
    await _redis_set_json(_key_strokes(room_id), strokes)
    await _publish(_channel_strokes(room_id), _patch_envelope(_channel_strokes(room_id), "strokes", stroke, _caller_id(cell_data, user_id)))
    return {"success": True, "output": {"strokeId": stroke["id"], "count": len(strokes)}}


@_action(drawer=True, locked=True)
async def _handle_clear_canvas(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    await _redis_set_json(_key_strokes(room_id), [])
    await _publish(_channel_strokes(room_id), _snapshot_envelope(_channel_strokes(room_id), [], _caller_id(cell_data, user_id)))
    return {"success": True, "output": {"cleared": True}}


@_action()
async def _handle_snapshot_request(room_id: str, state: Dict[str, Any], cell_data: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    sender_id = _caller_id(cell_data, user_id)
    strokes = await _load_list(_key_strokes(room_id))
    guesses = await _load_list(_key_guesses(room_id))

    await _publish(_channel_state(room_id), _snapshot_envelope(_channel_state(room_id), state, sender_id))
    await _publish(_channel_strokes(room_id), _snapshot_envelope(_channel_strokes(room_id), strokes, sender_id))
    await _publish(_channel_guesses(room_id), _snapshot_envelope(_channel_guesses(room_id), guesses, sender_id))

    output: Dict[str, Any] = {"state": state, "strokes": strokes, "guesses": guesses}
    if _is_drawer(state, sender_id):
        word = await _redis_get_json(_key_word(room_id), None)
        if word:
            output["secretWord"] = word
    return {"success": True, "output": output}


# ── Entry point ──────────────────────────────────────────────────────────────


_HANDLERS: Dict[str, Any] = {
    "join_game": _handle_join_game,
    "leave_game": _handle_leave_game,
    "start_game": _handle_start_game,
    "start_round": _handle_start_round,
    "next_round": _handle_next_round,
    "end_game": _handle_end_game,
    "get_secret": _handle_get_secret,
    "submit_guess": _handle_submit_guess,
    "hint": _handle_hint,
    "append_stroke": _handle_append_stroke,
    "clear_canvas": _handle_clear_canvas,
    "snapshot_request": _handle_snapshot_request,
}


async def execute_cell(
    cell_data: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Entry point called by ``cells_router`` (execute-ephemeral)."""
    action: str = str(cell_data.get("action") or "").strip()
    logger.debug("[party-game] execute_cell action=%s user_id=%s", action, user_id)
    handler = _HANDLERS.get(action)
    if handler is None:
        return {
            "success": False,
            "output": {},
            "error": f"Unknown action: '{action}'. Supported: {', '.join(sorted(_HANDLERS))}",
        }
    return await handler(cell_data, user_id)
