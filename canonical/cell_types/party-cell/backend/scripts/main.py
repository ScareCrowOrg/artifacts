"""
party-cell — Backend Script

Executed by cells_router via POST /api/v1/cells/execute-ephemeral (same
mechanism as ``planet-chat-cell``).  The script is discovered by *path
convention* — ``artifacts/canonical/cell_types/party-cell/backend/scripts/main.py``
— and must export an ``execute_cell(cell_data, user_id=None)`` entry point.

Supported actions
-----------------
join_room
    Add the calling participant to the room presence snapshot and publish it.
leave_room
    Remove the calling participant and publish the updated snapshot.
mute_toggle
    Flip the participant's ``isMuted`` flag.
tracks_update
    Update the participant's published ``tracks`` (e.g. screen share).
snapshot_request
    Publish the current participant snapshot to the channel.

Redis layout
------------
- Channel:   ``calls:room:{roomId}``      — WSS pub/sub; MUST match the
  frontend ``usePartyCalls`` contextId ``calls:room:{roomId}``.
- Snapshot:  ``calls:presence:{roomId}``  — JSON array of participants.

Presence contract
-----------------
Every action publishes a **snapshot** envelope (not an incremental patch).
``useDistributedState`` handles ``type: "snapshot"`` by replacing the
``participants`` branch with ``payload.state`` — bypassing the LWW
timestamp guard and avoiding index-based remove races.  The backend script
is the single source of truth for room presence; clients never publish
patches for this branch.

Security notes
--------------
- roomId is validated to be non-empty and to contain only safe characters.
- participantId defaults to the authenticated ``user_id`` injected by the
  router (never trusts client-supplied ids blindly).
- No user-supplied data is executed; only JSON-serialised values are stored.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

SNAPSHOT_TTL_SECONDS = 86_400  # 24 hours
_SAFE_ROOM_ID_RE = re.compile(r'^[\w:._-]{1,256}$')

# ── Redis connection helpers ─────────────────────────────────────────────────


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


# ── Key / channel helpers ────────────────────────────────────────────────────


def _room_id_is_safe(room_id: str) -> bool:
    """Return True if *room_id* consists only of safe characters."""
    return bool(_SAFE_ROOM_ID_RE.match(room_id))


def _snapshot_key(room_id: str) -> str:
    return f"calls:presence:{room_id}"


def _channel_name(room_id: str) -> str:
    return f"calls:room:{room_id}"


# ── Snapshot helpers ─────────────────────────────────────────────────────────


async def _load_participants(room_id: str) -> List[Dict[str, Any]]:
    """Return the current participant list for *room_id*, or []."""
    client = await _get_async_redis_client()
    try:
        raw = await client.get(_snapshot_key(room_id))
        if raw is None:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return []
    except Exception as exc:
        logger.warning("[party-cell] Failed to load participants: %s", exc)
        return []
    finally:
        await client.aclose()


async def _save_participants(room_id: str, participants: List[Dict[str, Any]]) -> None:
    """Persist the participant list to Redis with a 24-hour TTL."""
    client = await _get_async_redis_client()
    try:
        await client.set(
            _snapshot_key(room_id),
            json.dumps(participants),
            ex=SNAPSHOT_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning("[party-cell] Failed to save participants: %s", exc)
    finally:
        await client.aclose()


async def _publish_snapshot(
    room_id: str,
    participants: List[Dict[str, Any]],
    sender_id: str,
    timestamp: int,
) -> None:
    """Publish a snapshot envelope to the room channel (Redis PUBLISH)."""
    envelope = {
        "type": "snapshot",
        "contextId": _channel_name(room_id),
        "senderId": sender_id,
        "timestamp": timestamp,
        "payload": {
            "state": participants,
        },
    }
    client = await _get_async_redis_client()
    try:
        await client.publish(_channel_name(room_id), json.dumps(envelope))
    except Exception as exc:
        logger.warning("[party-cell] Failed to publish snapshot: %s", exc)
    finally:
        await client.aclose()


# ── Action handlers ──────────────────────────────────────────────────────────


async def _handle_join_room(
    cell_data: Dict[str, Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """
    Upsert the calling participant into the room presence snapshot.

    Match key: ``sessionId`` (NOT ``participantId``).  REV-1 (F4 gate,
    party-cell-mock-remote-user): a single user may hold SEVERAL parallel
    sessions in the same room (two tabs/windows).  Upserting by
    ``participantId = user_id`` made the LAST join REPLACE the FIRST — so the
    first session's tile had no presence entry and rendered as the generic
    "Usuário Remoto".  Matching by ``sessionId`` makes each session its OWN
    presence entry: the two sessions COEXIST, and a subscriber's lookup
    ``parts.find(p => p.sessionId === ownerId)`` resolves BOTH to the correct
    ``displayName``.  ``participantId`` is still stored on the entry (kept for
    compatibility / other actions).

    Expected keys in *cell_data*:
        roomId       (str)  — room identifier
        sessionId    (str)  — Cloudflare session id of the caller
        participantId (str, optional) — defaults to user_id
        displayName  (str, optional) — defaults to user name / user_id
        tracks       (list, optional) — defaults to [] (Caso B: join silent)
        trackNames   (list, optional) — the publisher's NATIVE MediaStreamTrack
          ids (sender.track.id) as registered on the Cloudflare SFU
        isMuted      (bool, optional) — defaults to False
    """
    room_id: str = cell_data.get("roomId", "").strip()
    session_id: str = cell_data.get("sessionId", "").strip()

    if not room_id:
        return {"success": False, "output": {}, "error": "roomId is required"}
    if not _room_id_is_safe(room_id):
        return {"success": False, "output": {}, "error": "roomId contains invalid characters"}
    if not session_id:
        return {"success": False, "output": {}, "error": "sessionId is required"}

    participant_id: str = cell_data.get("participantId") or (user_id or session_id)

    # Resolve a human-readable name from the authenticated user when available
    display_name: str = cell_data.get("displayName") or ""
    if not display_name:
        current_user = cell_data.get("_current_user")
        if current_user is not None:
            display_name = getattr(current_user, "name", "") or ""
    if not display_name:
        display_name = participant_id

    tracks: List[str] = cell_data.get("tracks") or []
    track_names: Optional[List[str]] = cell_data.get("trackNames")
    joined_at: int = int(cell_data.get("joinedAt") or int(time.time() * 1000))

    participant = {
        "participantId": participant_id,
        "sessionId": session_id,
        "displayName": display_name,
        "tracks": tracks,
        "isMuted": bool(cell_data.get("isMuted", False)),
        "joinedAt": joined_at,
    }
    if track_names:
        participant["trackNames"] = track_names

    participants = await _load_participants(room_id)
    replaced = False
    # REV-1 (F4 gate): upsert/match by sessionId — NOT participantId.  A reconnect
    # / refresh of the SAME session replaces its own entry (joinedAt preserved);
    # a SECOND session of the same user (parallel tab) is APPENDED so the two
    # coexist in presence (each resolves to its own tile/displayName).
    for idx, existing in enumerate(participants):
        if existing.get("sessionId") == session_id:
            # Preserve joinedAt so a reconnect does not reset the join time
            participant["joinedAt"] = existing.get("joinedAt", joined_at)
            participants[idx] = participant
            replaced = True
            break
    if not replaced:
        participants.append(participant)

    await _save_participants(room_id, participants)
    await _publish_snapshot(room_id, participants, participant_id, int(time.time() * 1000))

    logger.info(
        "[party-cell] join_room: room=%s participant=%s session=%s count=%d",
        room_id, participant_id, session_id, len(participants),
    )
    return {
        "success": True,
        "output": {
            "participants": participants,
            "count": len(participants),
        },
    }


async def _handle_leave_room(
    cell_data: Dict[str, Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """
    Remove the calling session from the room presence snapshot.

    Match key: ``sessionId`` when present (REV-1, F4 gate — a parallel tab of
    the same user must SURVIVE this leave, so only this session's entry is
    removed).  Falls back to ``participantId`` for legacy clients that only
    send the participant (note: that removes ALL of the user's sessions).

    Expected keys in *cell_data*:
        roomId       (str)
        sessionId    (str, optional) — REV-1: the exact session to remove
        participantId (str, optional) — defaults to user_id (legacy fallback)
    """
    room_id: str = cell_data.get("roomId", "").strip()
    if not room_id:
        return {"success": False, "output": {}, "error": "roomId is required"}
    if not _room_id_is_safe(room_id):
        return {"success": False, "output": {}, "error": "roomId contains invalid characters"}

    session_id: str = (cell_data.get("sessionId") or "").strip()
    participant_id: str = cell_data.get("participantId") or (user_id or "unknown")

    participants = await _load_participants(room_id)
    if session_id:
        remaining = [p for p in participants if p.get("sessionId") != session_id]
    else:
        # Legacy compat: no sessionId in payload → remove by participantId.
        remaining = [p for p in participants if p.get("participantId") != participant_id]

    if len(remaining) != len(participants):
        await _save_participants(room_id, remaining)
        await _publish_snapshot(room_id, remaining, participant_id, int(time.time() * 1000))

    logger.info(
        "[party-cell] leave_room: room=%s session=%s participant=%s remaining=%d",
        room_id, session_id or "(none)", participant_id, len(remaining),
    )
    return {
        "success": True,
        "output": {
            "participants": remaining,
            "count": len(remaining),
        },
    }


async def _handle_mute_toggle(
    cell_data: Dict[str, Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """
    Flip the calling session's ``isMuted`` flag and publish the snapshot.

    Match key: ``sessionId`` when present (REV-1, F4 gate — with multi-session
    presence a participantId match would flip the WRONG session when the same
    user has 2 parallel sessions).  Falls back to ``participantId`` for legacy
    clients.

    Expected keys in *cell_data*:
        roomId       (str)
        sessionId    (str, optional) — REV-1: target the exact session
        participantId (str, optional) — defaults to user_id (legacy fallback)
        isMuted      (bool, optional) — when provided, set to this value
    """
    room_id: str = cell_data.get("roomId", "").strip()
    if not room_id:
        return {"success": False, "output": {}, "error": "roomId is required"}
    if not _room_id_is_safe(room_id):
        return {"success": False, "output": {}, "error": "roomId contains invalid characters"}

    session_id: str = (cell_data.get("sessionId") or "").strip()
    participant_id: str = cell_data.get("participantId") or (user_id or "unknown")

    participants = await _load_participants(room_id)
    new_muted: Optional[bool] = None
    for p in participants:
        if session_id:
            match = p.get("sessionId") == session_id
        else:
            match = p.get("participantId") == participant_id
        if match:
            if "isMuted" in cell_data:
                new_muted = bool(cell_data["isMuted"])
            else:
                new_muted = not bool(p.get("isMuted", False))
            p["isMuted"] = new_muted
            break

    if new_muted is not None:
        await _save_participants(room_id, participants)
        await _publish_snapshot(room_id, participants, participant_id, int(time.time() * 1000))

    logger.info(
        "[party-cell] mute_toggle: room=%s participant=%s muted=%s",
        room_id, participant_id, new_muted,
    )
    return {
        "success": True,
        "output": {
            "participants": participants,
            "count": len(participants),
            "isMuted": new_muted,
        },
    }


async def _handle_tracks_update(
    cell_data: Dict[str, Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """
    Update the calling session's published tracks (e.g. after screen share).

    Match key: ``sessionId`` when present (REV-1, F4 gate — same rationale as
    mute_toggle: with multi-session presence, a participantId match would
    update the WRONG session of the same user).  Falls back to
    ``participantId`` for legacy clients.

    Expected keys in *cell_data*:
        roomId       (str)
        sessionId    (str, optional) — REV-1: target the exact session
        participantId (str, optional) — defaults to user_id (legacy fallback)
        tracks       (list) — new list of TrackType values
        trackNames   (list, optional) — the publisher's NATIVE MediaStreamTrack
          ids (sender.track.id) as registered on the Cloudflare SFU
    """
    room_id: str = cell_data.get("roomId", "").strip()
    if not room_id:
        return {"success": False, "output": {}, "error": "roomId is required"}
    if not _room_id_is_safe(room_id):
        return {"success": False, "output": {}, "error": "roomId contains invalid characters"}

    session_id: str = (cell_data.get("sessionId") or "").strip()
    participant_id: str = cell_data.get("participantId") or (user_id or "unknown")
    tracks: List[str] = cell_data.get("tracks") or []
    track_names: Optional[List[str]] = cell_data.get("trackNames")

    participants = await _load_participants(room_id)
    updated = False
    for p in participants:
        if session_id:
            match = p.get("sessionId") == session_id
        else:
            match = p.get("participantId") == participant_id
        if match:
            p["tracks"] = tracks
            if track_names:
                p["trackNames"] = track_names
            updated = True
            break

    if updated:
        await _save_participants(room_id, participants)
        await _publish_snapshot(room_id, participants, participant_id, int(time.time() * 1000))

    logger.info(
        "[party-cell] tracks_update: room=%s participant=%s tracks=%s",
        room_id, participant_id, tracks,
    )
    return {
        "success": True,
        "output": {
            "participants": participants,
            "count": len(participants),
        },
    }


async def _handle_snapshot_request(
    cell_data: Dict[str, Any],
    sender_id: str,
) -> Dict[str, Any]:
    """
    Publish the current participant snapshot to the room channel.

    Expected keys in *cell_data*:
        roomId (str)
    """
    room_id: str = cell_data.get("roomId", "").strip()
    if not room_id:
        return {"success": False, "output": {}, "error": "roomId is required"}
    if not _room_id_is_safe(room_id):
        return {"success": False, "output": {}, "error": "roomId contains invalid characters"}

    participants = await _load_participants(room_id)
    await _publish_snapshot(room_id, participants, sender_id, int(time.time() * 1000))

    logger.info(
        "[party-cell] snapshot_request: room=%s count=%d",
        room_id, len(participants),
    )
    return {
        "success": True,
        "output": {
            "participants": participants,
            "count": len(participants),
        },
    }


# ── Entry point ──────────────────────────────────────────────────────────────


async def execute_cell(
    cell_data: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Entry point called by cells_router.

    Args:
        cell_data: Payload from the execute-ephemeral request.  Must contain:
            - action (str): "join_room" | "leave_room" | "mute_toggle"
              | "tracks_update" | "snapshot_request"
            - roomId  (str): Room identifier
            Additional keys depend on the action (see handler docstrings).
        user_id: Authenticated user ID injected by the router middleware.

    Returns:
        Dict with ``{ success, output }`` or ``{ success, output, error }``.
    """
    action: str = cell_data.get("action", "").strip()

    logger.debug("[party-cell] execute_cell action=%s user_id=%s", action, user_id)

    if action == "join_room":
        return await _handle_join_room(cell_data, user_id)
    if action == "leave_room":
        return await _handle_leave_room(cell_data, user_id)
    if action == "mute_toggle":
        return await _handle_mute_toggle(cell_data, user_id)
    if action == "tracks_update":
        return await _handle_tracks_update(cell_data, user_id)
    if action == "snapshot_request":
        sender_id = cell_data.get("senderId") or (user_id or "client")
        return await _handle_snapshot_request(cell_data, sender_id)

    return {
        "success": False,
        "output": {},
        "error": (
            "Unknown action: '%s'. Supported: join_room, leave_room, "
            "mute_toggle, tracks_update, snapshot_request"
        ) % action,
    }


# ── CLI testing helper (dev-only — excluded from coverage) ───────────────────

if __name__ == "__main__":  # pragma: no cover
    import asyncio
    import sys

    test_payload = {
        "action": "join_room",
        "roomId": "test-room",
        "sessionId": "test-session",
    }

    if len(sys.argv) > 1:
        try:
            test_payload = json.loads(sys.argv[1])
        except json.JSONDecodeError as exc:
            print(f"Error parsing JSON argument: {exc}", file=sys.stderr)
            sys.exit(1)

    result = asyncio.run(execute_cell(test_payload, user_id="cli-user"))
    print(json.dumps(result, indent=2))
