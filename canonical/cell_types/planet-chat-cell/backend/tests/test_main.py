"""
Tests for planet-chat-cell backend (main.py).

Coverage targets:
- send_message: publishes patch to correct channel, updates snapshot
- snapshot_request: reads snapshot and publishes it
- Context isolation: contextId A does not affect contextId B
- Edge cases: empty contextId, empty message, unknown action
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the scripts directory to the path so we can import main directly
cell_root = Path(__file__).parent.parent
sys.path.insert(0, str(cell_root / "scripts"))

import main  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _make_async_redis(get_return=None, set_return=None, publish_return=None):
    """
    Build a mock async Redis client with pre-configured return values.

    ``get_return`` can be:
      - None        → client.get() returns None
      - a list      → client.get() returns json.dumps(list)
      - a raw str   → client.get() returns that string
    """
    client = MagicMock()
    client.aclose = AsyncMock()

    if get_return is None:
        client.get = AsyncMock(return_value=None)
    elif isinstance(get_return, list):
        client.get = AsyncMock(return_value=json.dumps(get_return))
    else:
        client.get = AsyncMock(return_value=get_return)

    client.set = AsyncMock(return_value=set_return)
    client.publish = AsyncMock(return_value=publish_return)

    return client


# ─────────────────────────────────────────────────────────────────────────────
# send_message
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestSendMessage:

    async def test_send_message_publishes_to_correct_channel(self):
        """send_message must PUBLISH to planet-chat:{contextId}."""
        mock_client = _make_async_redis(get_return=[])

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {
                    "action": "send_message",
                    "contextId": "room-abc",
                    "message": "Hello world",
                    "senderId": "user-1",
                },
                user_id="user-1",
            )

        assert result["success"] is True

        # publish() must have been called on the correct channel
        calls = mock_client.publish.call_args_list
        assert len(calls) == 1
        channel, raw_payload = calls[0].args
        assert channel == "planet-chat:room-abc"

        payload = json.loads(raw_payload)
        assert payload["type"] == "patch"
        assert payload["contextId"] == "planet-chat:room-abc"
        assert payload["payload"]["branch"] == "messages"
        operations = payload["payload"]["operations"]
        assert len(operations) == 1
        assert operations[0]["op"] == "add"
        assert operations[0]["path"] == "/-"
        assert operations[0]["value"]["text"] == "Hello world"

    async def test_send_message_updates_snapshot(self):
        """send_message must persist the updated message list to Redis."""
        existing = [
            {"id": "100-user-0", "text": "First", "senderId": "user-0", "timestamp": 100}
        ]
        mock_client = _make_async_redis(get_return=existing)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {
                    "action": "send_message",
                    "contextId": "room-abc",
                    "message": "Second",
                    "senderId": "user-1",
                },
            )

        assert result["success"] is True

        # set() must have been called with a list containing both messages
        set_calls = mock_client.set.call_args_list
        assert len(set_calls) == 1
        key, raw_data = set_calls[0].args
        assert key == "planet-chat:snapshot:room-abc"
        saved = json.loads(raw_data)
        assert len(saved) == 2
        assert saved[0]["text"] == "First"
        assert saved[1]["text"] == "Second"

    async def test_send_message_returns_message_object(self):
        """execute_cell must return the new message object in output."""
        mock_client = _make_async_redis(get_return=[])

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {
                    "action": "send_message",
                    "contextId": "room-xyz",
                    "message": "Test message",
                    "senderId": "alice",
                }
            )

        assert result["success"] is True
        assert result["output"]["message"]["text"] == "Test message"
        assert result["output"]["message"]["senderId"] == "alice"
        assert result["output"]["channel"] == "planet-chat:room-xyz"

    async def test_send_message_rejects_empty_context_id(self):
        """execute_cell must reject send_message with an empty contextId."""
        result = await main.execute_cell(
            {"action": "send_message", "contextId": "", "message": "hi"}
        )
        assert result["success"] is False
        assert "contextid" in result["error"].lower()

    async def test_send_message_rejects_empty_message(self):
        """execute_cell must reject send_message with an empty message."""
        result = await main.execute_cell(
            {"action": "send_message", "contextId": "room-abc", "message": ""}
        )
        assert result["success"] is False
        assert "message" in result["error"].lower()

    async def test_send_message_rejects_unsafe_context_id(self):
        """execute_cell must reject contextIds containing unsafe characters."""
        result = await main.execute_cell(
            {
                "action": "send_message",
                "contextId": "room; DROP TABLE messages;--",
                "message": "injection attempt",
            }
        )
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# snapshot_request
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestSnapshotRequest:

    async def test_snapshot_request_publishes_current_state(self):
        """snapshot_request must PUBLISH a snapshot message with current messages."""
        existing = [
            {"id": "1-u1", "text": "Hi", "senderId": "u1", "timestamp": 1},
            {"id": "2-u2", "text": "Hey", "senderId": "u2", "timestamp": 2},
        ]
        mock_client = _make_async_redis(get_return=existing)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "snapshot_request", "contextId": "room-snap"}
            )

        assert result["success"] is True
        assert result["output"]["count"] == 2

        calls = mock_client.publish.call_args_list
        assert len(calls) == 1
        channel, raw_payload = calls[0].args
        assert channel == "planet-chat:room-snap"

        payload = json.loads(raw_payload)
        assert payload["type"] == "snapshot"
        assert payload["contextId"] == "planet-chat:room-snap"
        assert len(payload["payload"]["state"]) == 2

    async def test_snapshot_request_empty_channel(self):
        """snapshot_request on an empty channel must return empty list."""
        mock_client = _make_async_redis(get_return=None)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "snapshot_request", "contextId": "empty-room"}
            )

        assert result["success"] is True
        assert result["output"]["count"] == 0
        assert result["output"]["messages"] == []

    async def test_snapshot_request_rejects_empty_context_id(self):
        """snapshot_request must reject an empty contextId."""
        result = await main.execute_cell(
            {"action": "snapshot_request", "contextId": ""}
        )
        assert result["success"] is False
        assert "contextid" in result["error"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Context isolation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestContextIsolation:

    async def test_two_contexts_use_different_channels(self):
        """Messages for contextId A must be published to channel A, not channel B."""
        mock_client_a = _make_async_redis(get_return=[])
        mock_client_b = _make_async_redis(get_return=[])

        # Track which clients were used per call
        clients_used: list = []

        def _make_client():
            c = _make_async_redis(get_return=[])
            clients_used.append(c)
            return c

        async_make = AsyncMock(side_effect=_make_client)

        with patch("main._get_async_redis_client", new=async_make):
            await main.execute_cell(
                {"action": "send_message", "contextId": "ctx-A", "message": "Msg A"}
            )
            await main.execute_cell(
                {"action": "send_message", "contextId": "ctx-B", "message": "Msg B"}
            )

        # Each call creates two client instances (one for load, one for publish)
        # Just verify the publish channels were different
        all_publish_calls = []
        for client in clients_used:
            all_publish_calls.extend(client.publish.call_args_list)

        channels = [c.args[0] for c in all_publish_calls]
        assert "planet-chat:ctx-A" in channels
        assert "planet-chat:ctx-B" in channels

        # Verify channel A payload contains Msg A
        channel_a_payloads = [
            json.loads(c.args[1])
            for c in all_publish_calls
            if c.args[0] == "planet-chat:ctx-A"
        ]
        assert any(
            op["value"]["text"] == "Msg A"
            for p in channel_a_payloads
            for op in p.get("payload", {}).get("operations", [])
        )

    async def test_snapshot_keys_are_isolated(self):
        """Snapshots for contextId A and B must use different Redis keys."""
        key_a = main._snapshot_key("ctx-A")
        key_b = main._snapshot_key("ctx-B")
        assert key_a != key_b
        assert "ctx-A" in key_a
        assert "ctx-B" in key_b


# ─────────────────────────────────────────────────────────────────────────────
# Unknown action / edge cases
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestEdgeCases:

    async def test_unknown_action_returns_error(self):
        """An unknown action must return success=False with a descriptive error."""
        result = await main.execute_cell(
            {"action": "fly_to_the_moon", "contextId": "ctx-x"}
        )
        assert result["success"] is False
        assert "fly_to_the_moon" in result["error"]

    async def test_missing_action_returns_error(self):
        """A missing action key must return success=False."""
        result = await main.execute_cell({"contextId": "ctx-x"})
        assert result["success"] is False

    async def test_user_id_used_as_sender_id_fallback(self):
        """user_id from the router should be used as senderId when not provided."""
        mock_client = _make_async_redis(get_return=[])

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "send_message", "contextId": "ctx-x", "message": "Hi"},
                user_id="injected-user",
            )

        assert result["success"] is True
        msg = result["output"]["message"]
        assert msg["senderId"] == "injected-user"
