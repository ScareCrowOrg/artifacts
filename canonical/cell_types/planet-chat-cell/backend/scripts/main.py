"""
planet-chat-cell — Backend Script

Executed by cells_router via POST /api/v1/cells/execute-ephemeral or
POST /api/v1/cells/{cell_id}/execute.

Supported actions
-----------------
send_message
    Formats a JSON Patch (RFC 6902 add operation) and publishes it to the
    Redis channel ``planet-chat:{contextId}``.  Also updates the persistent
    snapshot stored at ``planet-chat:snapshot:{contextId}``.

snapshot_request
    Reads the current snapshot from Redis and publishes a ``snapshot`` message
    back to the channel so that newly connected clients receive the full state.

Security notes
--------------
- contextId is validated to be non-empty and to contain only safe characters
  (alphanumeric, hyphens, underscores, colons) before use as a Redis key.
- No user-supplied data is executed; only JSON-serialised values are stored.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Redis connection helpers ─────────────────────────────────────────────────

SNAPSHOT_TTL_SECONDS = 86_400  # 24 hours

_SAFE_CONTEXT_ID_RE = re.compile(r'^[\w:._-]{1,256}$')


def _context_id_is_safe(context_id: str) -> bool:
    """Return True if *context_id* consists only of safe characters."""
    return bool(_SAFE_CONTEXT_ID_RE.match(context_id))


def _get_redis_client():
    """Return a synchronous Redis client using the project-wide L1 config."""
    import redis as _redis
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

    return _redis.Redis(**kwargs)


async def _get_async_redis_client():
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


# ── Snapshot helpers ─────────────────────────────────────────────────────────

def _snapshot_key(context_id: str) -> str:
    return f"planet-chat:snapshot:{context_id}"


def _channel_name(context_id: str) -> str:
    return f"planet-chat:{context_id}"


async def _load_snapshot(context_id: str) -> List[Dict[str, Any]]:
    """Return the current message list stored in the snapshot, or []."""
    client = await _get_async_redis_client()
    try:
        raw = await client.get(_snapshot_key(context_id))
        if raw is None:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return []
    except Exception as exc:
        logger.warning("[planet-chat] Failed to load snapshot: %s", exc)
        return []
    finally:
        await client.aclose()


async def _save_snapshot(context_id: str, messages: List[Dict[str, Any]]) -> None:
    """Persist the message list to Redis with a 24-hour TTL."""
    client = await _get_async_redis_client()
    try:
        await client.set(
            _snapshot_key(context_id),
            json.dumps(messages),
            ex=SNAPSHOT_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning("[planet-chat] Failed to save snapshot: %s", exc)
    finally:
        await client.aclose()


async def _publish(context_id: str, payload: Dict[str, Any]) -> None:
    """Publish a JSON-encoded message to the planet-chat channel."""
    client = await _get_async_redis_client()
    try:
        await client.publish(_channel_name(context_id), json.dumps(payload))
    finally:
        await client.aclose()


# ── Action handlers ──────────────────────────────────────────────────────────

async def _handle_send_message(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Append a new message to the chat history and notify all peers.

    Expected keys in *cell_data*:
        contextId  (str)  — channel / context identifier
        message    (str)  — message text
        senderId   (str, optional) — defaults to "anonymous"
        timestamp  (int, optional) — ms epoch; defaults to now
    """
    context_id: str = cell_data.get("contextId", "").strip()
    message: str = cell_data.get("message", "").strip()
    sender_id: str = cell_data.get("senderId", "anonymous")
    timestamp: int = cell_data.get("timestamp", int(time.time() * 1000))

    if not context_id:
        return {"success": False, "output": {}, "error": "contextId is required"}

    if not _context_id_is_safe(context_id):
        return {"success": False, "output": {}, "error": "contextId contains invalid characters"}

    if not message:
        return {"success": False, "output": {}, "error": "message is required and cannot be empty"}

    # Build the message object that will be appended
    msg_obj = {
        "id": f"{timestamp}-{sender_id}",
        "text": message,
        "senderId": sender_id,
        "timestamp": timestamp,
    }

    # Update the persistent snapshot
    messages = await _load_snapshot(context_id)
    messages.append(msg_obj)
    await _save_snapshot(context_id, messages)

    # Publish JSON Patch (RFC 6902 append operation) to all connected clients.
    # path='/-' is correct: useDistributedState passes store[branch] (the array)
    # as the patch target, so the root-append path '/-' maps to array.push().
    # contextId in the envelope MUST match the full channel name so that the
    # frontend's resolvedContextId filter (msg.contextId === resolvedContextId.value)
    # passes. resolvedContextId.value = `planet-chat:{roomId}` (prefixed).
    patch_envelope = {
        "type": "patch",
        "contextId": _channel_name(context_id),
        "senderId": sender_id,
        "timestamp": timestamp,
        "payload": {
            "branch": "messages",
            "operations": [
                {"op": "add", "path": "/-", "value": msg_obj}
            ],
        },
    }
    await _publish(context_id, patch_envelope)

    logger.info(
        "[planet-chat] send_message: contextId=%s sender=%s",
        context_id,
        sender_id,
    )
    # [DEBUG planet-chat B1] Log the full patch envelope and channel name for comparison
    logger.info(
        "[planet-chat][DEBUG] Published to channel='%s' with envelope.contextId='%s'. "
        "Frontend resolvedContextId = 'planet-chat:%s'. MATCH=%s",
        _channel_name(context_id),
        patch_envelope["contextId"],
        context_id,
        patch_envelope["contextId"] == f"planet-chat:{context_id}",
    )

    return {
        "success": True,
        "output": {
            "message": msg_obj,
            "channel": _channel_name(context_id),
        },
    }


async def _handle_snapshot_request(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return (and broadcast) the current message snapshot.

    Expected keys in *cell_data*:
        contextId  (str) — channel / context identifier
        senderId   (str, optional)
    """
    context_id: str = cell_data.get("contextId", "").strip()
    sender_id: str = cell_data.get("senderId", "anonymous")
    timestamp: int = int(time.time() * 1000)

    if not context_id:
        return {"success": False, "output": {}, "error": "contextId is required"}

    if not _context_id_is_safe(context_id):
        return {"success": False, "output": {}, "error": "contextId contains invalid characters"}

    messages = await _load_snapshot(context_id)

    snapshot_envelope = {
        "type": "snapshot",
        "contextId": _channel_name(context_id),
        "senderId": sender_id,
        "timestamp": timestamp,
        "payload": {
            "state": messages,
        },
    }
    await _publish(context_id, snapshot_envelope)

    logger.info(
        "[planet-chat] snapshot_request: contextId=%s messages=%d",
        context_id,
        len(messages),
    )
    # [DEBUG planet-chat B1] Log snapshot envelope contextId vs channel name
    logger.info(
        "[planet-chat][DEBUG] Snapshot published to channel='%s' with envelope.contextId='%s'. "
        "MATCH=%s",
        _channel_name(context_id),
        snapshot_envelope["contextId"],
        snapshot_envelope["contextId"] == f"planet-chat:{context_id}",
    )

    return {
        "success": True,
        "output": {
            "messages": messages,
            "count": len(messages),
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
            - action     (str): "send_message" | "snapshot_request"
            - contextId  (str): Channel / context identifier
            Additional keys depend on the action (see handler docstrings).
        user_id: Authenticated user ID injected by the router middleware.

    Returns:
        Dict with ``{ success, output }`` or ``{ success, output, error }``.
    """
    action: str = cell_data.get("action", "").strip()

    # Inject user_id as senderId when not explicitly provided
    if user_id and not cell_data.get("senderId"):
        cell_data = {**cell_data, "senderId": user_id}

    logger.debug("[planet-chat] execute_cell action=%s user_id=%s", action, user_id)
    # [DEBUG planet-chat B2] Log effective senderId after possible user_id injection
    logger.info(
        "[planet-chat][DEBUG] execute_cell — action=%s user_id=%s cell_data.senderId=%s injection_applied=%s",
        action,
        user_id,
        cell_data.get("senderId"),
        bool(user_id and not cell_data.get("senderId")),
    )

    if action == "send_message":
        return await _handle_send_message(cell_data)

    if action == "snapshot_request":
        return await _handle_snapshot_request(cell_data)

    return {
        "success": False,
        "output": {},
        "error": f"Unknown action: '{action}'. Supported: send_message, snapshot_request",
    }


# ── CLI testing helper ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    test_payload = {
        "action": "send_message",
        "contextId": "test-context",
        "message": "Hello from CLI",
        "senderId": "cli-user",
    }

    if len(sys.argv) > 1:
        try:
            test_payload = json.loads(sys.argv[1])
        except json.JSONDecodeError as exc:
            print(f"Error parsing JSON argument: {exc}", file=sys.stderr)
            sys.exit(1)

    result = asyncio.run(execute_cell(test_payload, user_id="cli-user"))
    print(json.dumps(result, indent=2))
