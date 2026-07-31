"""
Tests for party-cell backend (main.py).

Coverage targets (RULESET.md Rule 3.1):
- join_room: upserts participant into the snapshot, publishes a snapshot envelope
- leave_room: removes the participant and publishes the updated snapshot
- mute_toggle: flips isMuted and publishes
- tracks_update: updates the participant's tracks and publishes
- snapshot_request: publishes the current participant list
- Edge cases: missing roomId, unsafe roomId, missing sessionId, unknown action
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


def _make_async_redis(get_return=None):
    """Build a mock async Redis client with a pre-configured get() return."""
    client = MagicMock()
    client.aclose = AsyncMock()

    if get_return is None:
        client.get = AsyncMock(return_value=None)
    elif isinstance(get_return, list):
        client.get = AsyncMock(return_value=json.dumps(get_return))
    else:
        client.get = AsyncMock(return_value=get_return)

    client.set = AsyncMock(return_value=True)
    client.publish = AsyncMock(return_value=1)

    return client


def _last_publish(client):
    """Return the (channel, payload) of the last publish call."""
    assert client.publish.call_count == 1
    return client.publish.call_args.args


def _sample_user(name="Alice"):
    user = MagicMock()
    user.id = "user-alice"
    user.name = name
    return user


# ─────────────────────────────────────────────────────────────────────────────
# join_room
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestJoinRoom:

    async def test_join_room_publishes_snapshot(self):
        """join_room must add the participant and PUBLISH a snapshot envelope."""
        mock_client = _make_async_redis(get_return=[])

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {
                    "action": "join_room",
                    "roomId": "planet-lobby",
                    "sessionId": "session-a",
                },
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["count"] == 1

        channel, raw_payload = _last_publish(mock_client)
        assert channel == "calls:room:planet-lobby"

        payload = json.loads(raw_payload)
        assert payload["type"] == "snapshot"
        assert payload["contextId"] == "calls:room:planet-lobby"
        state = payload["payload"]["state"]
        assert len(state) == 1
        assert state[0]["participantId"] == "user-alice"
        assert state[0]["sessionId"] == "session-a"
        assert state[0]["tracks"] == ["mic", "camera"]

        # Snapshot must be persisted to the presence key
        key, raw_saved = mock_client.set.call_args.args
        assert key == "calls:presence:planet-lobby"
        assert len(json.loads(raw_saved)) == 1

    async def test_join_room_uses_display_name_from_user(self):
        """displayName defaults to the authenticated user's name."""
        mock_client = _make_async_redis(get_return=[])
        current_user = _sample_user("Alice")

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {
                    "action": "join_room",
                    "roomId": "room-1",
                    "sessionId": "sess-1",
                    "_current_user": current_user,
                },
                user_id="user-alice",
            )

        assert result["success"] is True
        _, raw_payload = _last_publish(mock_client)
        state = json.loads(raw_payload)["payload"]["state"]
        assert state[0]["displayName"] == "Alice"

    async def test_join_room_upserts_existing_participant(self):
        """Re-joining must replace the existing entry (dedup by participantId)."""
        existing = [{
            "participantId": "user-alice",
            "sessionId": "old-session",
            "displayName": "Alice",
            "tracks": ["mic", "camera"],
            "isMuted": False,
            "joinedAt": 100,
        }]
        mock_client = _make_async_redis(get_return=existing)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {
                    "action": "join_room",
                    "roomId": "room-1",
                    "sessionId": "new-session",
                },
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["count"] == 1
        _, raw_payload = _last_publish(mock_client)
        state = json.loads(raw_payload)["payload"]["state"]
        assert len(state) == 1
        assert state[0]["sessionId"] == "new-session"
        # joinedAt preserved on upsert
        assert state[0]["joinedAt"] == 100

    async def test_join_room_rejects_empty_room_id(self):
        result = await main.execute_cell(
            {"action": "join_room", "roomId": "", "sessionId": "s1"}
        )
        assert result["success"] is False
        assert "roomid" in result["error"].lower()

    async def test_join_room_rejects_unsafe_room_id(self):
        result = await main.execute_cell(
            {"action": "join_room", "roomId": "room; DROP TABLE;--", "sessionId": "s1"}
        )
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()

    async def test_join_room_rejects_missing_session_id(self):
        result = await main.execute_cell(
            {"action": "join_room", "roomId": "room-1"}
        )
        assert result["success"] is False
        assert "sessionid" in result["error"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# leave_room
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestLeaveRoom:

    async def test_leave_room_removes_participant(self):
        """leave_room must remove the participant and publish the snapshot."""
        existing = [
            {"participantId": "user-alice", "sessionId": "s-a"},
            {"participantId": "user-bob", "sessionId": "s-b"},
        ]
        mock_client = _make_async_redis(get_return=existing)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "leave_room", "roomId": "room-1"},
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["count"] == 1
        _, raw_payload = _last_publish(mock_client)
        state = json.loads(raw_payload)["payload"]["state"]
        assert [p["participantId"] for p in state] == ["user-bob"]

    async def test_leave_room_absent_participant_still_succeeds(self):
        """leave_room for a user not in the room must not error."""
        existing = [{"participantId": "user-bob", "sessionId": "s-b"}]
        mock_client = _make_async_redis(get_return=existing)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "leave_room", "roomId": "room-1"},
                user_id="user-alice",
            )

        assert result["success"] is True
        # No publish when nothing changed
        assert mock_client.publish.call_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# mute_toggle
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestMuteToggle:

    async def test_mute_toggle_flips_is_muted(self):
        existing = [{"participantId": "user-alice", "isMuted": False}]
        mock_client = _make_async_redis(get_return=existing)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "mute_toggle", "roomId": "room-1"},
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["isMuted"] is True
        _, raw_payload = _last_publish(mock_client)
        state = json.loads(raw_payload)["payload"]["state"]
        assert state[0]["isMuted"] is True

    async def test_mute_toggle_explicit_value(self):
        existing = [{"participantId": "user-alice", "isMuted": True}]
        mock_client = _make_async_redis(get_return=existing)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "mute_toggle", "roomId": "room-1", "isMuted": False},
                user_id="user-alice",
            )

        assert result["output"]["isMuted"] is False


# ─────────────────────────────────────────────────────────────────────────────
# tracks_update
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestTracksUpdate:

    async def test_tracks_update_replaces_tracks(self):
        existing = [{"participantId": "user-alice", "tracks": ["mic", "camera"]}]
        mock_client = _make_async_redis(get_return=existing)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {
                    "action": "tracks_update",
                    "roomId": "room-1",
                    "tracks": ["mic", "camera", "screen"],
                },
                user_id="user-alice",
            )

        assert result["success"] is True
        _, raw_payload = _last_publish(mock_client)
        state = json.loads(raw_payload)["payload"]["state"]
        assert state[0]["tracks"] == ["mic", "camera", "screen"]


# ─────────────────────────────────────────────────────────────────────────────
# snapshot_request
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestSnapshotRequest:

    async def test_snapshot_request_publishes_current_state(self):
        existing = [
            {"participantId": "user-alice", "sessionId": "s-a"},
            {"participantId": "user-bob", "sessionId": "s-b"},
        ]
        mock_client = _make_async_redis(get_return=existing)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "snapshot_request", "roomId": "room-1"},
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["count"] == 2

        channel, raw_payload = _last_publish(mock_client)
        assert channel == "calls:room:room-1"
        payload = json.loads(raw_payload)
        assert payload["type"] == "snapshot"
        assert len(payload["payload"]["state"]) == 2

    async def test_snapshot_request_empty_room(self):
        mock_client = _make_async_redis(get_return=None)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "snapshot_request", "roomId": "empty-room"}
            )

        assert result["success"] is True
        assert result["output"]["count"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Validation branches (empty / unsafe roomId for every action)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestValidationBranches:

    async def test_leave_room_rejects_empty_room_id(self):
        result = await main.execute_cell({"action": "leave_room", "roomId": ""})
        assert result["success"] is False
        assert "roomid" in result["error"].lower()

    async def test_leave_room_rejects_unsafe_room_id(self):
        result = await main.execute_cell(
            {"action": "leave_room", "roomId": "bad;room"}
        )
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()

    async def test_mute_toggle_rejects_empty_room_id(self):
        result = await main.execute_cell({"action": "mute_toggle", "roomId": ""})
        assert result["success"] is False
        assert "roomid" in result["error"].lower()

    async def test_mute_toggle_rejects_unsafe_room_id(self):
        result = await main.execute_cell(
            {"action": "mute_toggle", "roomId": "bad;room"}
        )
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()

    async def test_tracks_update_rejects_empty_room_id(self):
        result = await main.execute_cell(
            {"action": "tracks_update", "roomId": "", "tracks": []}
        )
        assert result["success"] is False
        assert "roomid" in result["error"].lower()

    async def test_tracks_update_rejects_unsafe_room_id(self):
        result = await main.execute_cell(
            {"action": "tracks_update", "roomId": "bad;room", "tracks": []}
        )
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()

    async def test_snapshot_request_rejects_empty_room_id(self):
        result = await main.execute_cell({"action": "snapshot_request", "roomId": ""})
        assert result["success"] is False
        assert "roomid" in result["error"].lower()

    async def test_snapshot_request_rejects_unsafe_room_id(self):
        result = await main.execute_cell(
            {"action": "snapshot_request", "roomId": "bad;room"}
        )
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Redis failure tolerance (defensive exception branches)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestRedisFailureTolerance:

    async def test_load_failure_falls_back_to_empty(self):
        """A Redis read failure must not crash the action (falls back to [])."""
        mock_client = _make_async_redis()
        mock_client.get = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "join_room", "roomId": "room-1", "sessionId": "s1"},
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["count"] == 1

    async def test_save_failure_does_not_crash(self):
        """A Redis write failure during save must not crash the action."""
        mock_client = _make_async_redis(get_return=[])
        mock_client.set = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "join_room", "roomId": "room-1", "sessionId": "s1"},
                user_id="user-alice",
            )

        assert result["success"] is True

    async def test_publish_failure_does_not_crash(self):
        """A Redis publish failure must not crash the action."""
        mock_client = _make_async_redis(get_return=[])
        mock_client.publish = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "join_room", "roomId": "room-1", "sessionId": "s1"},
                user_id="user-alice",
            )

        assert result["success"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestEdgeCases:

    async def test_unknown_action_returns_error(self):
        result = await main.execute_cell(
            {"action": "fly_to_the_moon", "roomId": "room-1"}
        )
        assert result["success"] is False
        assert "fly_to_the_moon" in result["error"]

    async def test_missing_action_returns_error(self):
        result = await main.execute_cell({"roomId": "room-1"})
        assert result["success"] is False

    async def test_keys_are_isolated_per_room(self):
        """Different rooms must use different Redis keys/channels."""
        assert main._snapshot_key("room-a") != main._snapshot_key("room-b")
        assert main._channel_name("room-a") == "calls:room:room-a"
        assert main._channel_name("room-b") == "calls:room:room-b"
