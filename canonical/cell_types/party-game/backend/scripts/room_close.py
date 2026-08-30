"""
party-game room-close helpers — host key + per-room reset.

Kept separate from ``main.py`` so that module stays under the RULESET.md
650-line limit (Rule 1.1).  ``close_room`` imports ``main`` lazily (at call
time) so there is no import-time circular dependency — ``main`` already imports
this module, but only calls ``close_room`` after ``main`` is fully loaded.  The
lazy import also keeps unit tests patching ``main._get_async_redis_client``.
"""

from typing import Any, Dict


def host_key(room_id: str) -> str:
    """Redis key holding the room's creator (host) participant id."""
    return f"game:host:{room_id}"


async def close_room(
    room_id: str,
    cell_data: Dict[str, Any],
    user_id: Any,
) -> Dict[str, Any]:
    """Reset a room's game state + presence + host key.

    Host-gated: only the room creator (``_caller_id`` == the stored host) may
    close.  A non-host caller gets ``success: False``.  Every game key is
    cleared and a reset snapshot is published to the state channel so connected
    clients converge on a fresh lobby immediately.

    The host key is cleared (set to ``None``) so a re-created room using the
    same name starts with no host — a fresh "Abrir Sala" sets a new creator with
    no leftover 24h-TTL host from the previous session.
    """
    import main  # lazy — see module docstring (no import-time circular dep)

    sender_id = main._caller_id(cell_data, user_id)
    room_host_key = host_key(room_id)

    host = await main._redis_get_json(room_host_key, None)
    if host != sender_id:
        return {"success": False, "output": {}, "error": "only the room creator can close the room"}

    await main._redis_set_json(main._key_state(room_id), {})
    await main._redis_set_json(main._key_strokes(room_id), [])
    await main._redis_set_json(main._key_guesses(room_id), [])
    await main._redis_set_json(main._key_word(room_id), None)
    await main._redis_set_json(main._presence_key(room_id), [])
    await main._redis_set_json(room_host_key, None)
    await main._publish(
        main._channel_state(room_id),
        main._snapshot_envelope(main._channel_state(room_id), {}, sender_id),
    )

    return {"success": True, "output": {"closed": True}}
