"""
Tests for puyo-party-cell backend (main.py).

Coverage targets (RULESET.md Rule 3.1):
- ready: marks the caller ready; auto-starts when every rostered player is ready
- start_game: rejects <2 players / not-all-ready / already-running; issues seed
- submit_garbage: sanitizes amount, accumulates on the target, rejects invalid
- piece_locked: validates and records the compact grid
- game_over: arbitrates the winner (opponent of the reporter), idempotent
- snapshot_request: publishes AND returns state/participantId/participants
- Edge cases: missing/unsafe roomId for every action, unknown action, Redis
  failure tolerance, per-room lock busy rejection
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
    else:
        client.get = AsyncMock(return_value=json.dumps(get_return))

    client.set = AsyncMock(return_value=True)
    client.publish = AsyncMock(return_value=1)
    client.delete = AsyncMock(return_value=True)

    return client


def _last_publish(client):
    """Return the (channel, payload) of the last publish call."""
    assert client.publish.call_count >= 1
    return client.publish.call_args_list[-1].args


def _published_state(client):
    """Parse the state from the last published snapshot envelope."""
    _, raw = _last_publish(client)
    payload = json.loads(raw)
    assert payload["type"] == "snapshot"
    return payload["payload"]["state"]


def _waiting_state():
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


def _running_state(players=("user-alice", "user-bob")):
    return {
        "status": "running",
        "seed": 12345,
        "round": 1,
        "scores": {p: 0 for p in players},
        "readyFlags": {p: True for p in players},
        "garbagePending": {p: 0 for p in players},
        "grids": {},
        "gameOver": None,
    }


def _grid(value=0):
    """A valid compact 72-cell grid."""
    return [value] * 72


def _presence(players):
    return [{"participantId": p, "displayName": p.replace("user-", "")} for p in players]


# ─────────────────────────────────────────────────────────────────────────────
# ready
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestReady:

    async def test_ready_marks_caller_and_publishes(self):
        state = _waiting_state()
        mock_client = _make_async_redis(get_return=state)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "ready", "roomId": "room-1"}, user_id="user-alice")

        assert result["success"] is True
        assert result["output"]["readyFlags"]["user-alice"] is True
        channel, _ = _last_publish(mock_client)
        assert channel == "puyo:game:room-1"

    async def test_ready_autostarts_when_all_players_ready(self):
        """Both players ready (one from state, one from this call) → start."""
        state = _waiting_state()
        state["readyFlags"] = {"user-bob": True}
        mock_client = _make_async_redis(get_return=state)
        mock_client.get.side_effect = None
        mock_client.get.return_value = json.dumps(state)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            with patch("main._generate_seed", return_value=777):
                result = await main.execute_cell({"action": "ready", "roomId": "room-1"}, user_id="user-alice")

        assert result["success"] is True
        assert result["output"]["status"] == "running"
        assert result["output"]["seed"] == 777

        published = _published_state(mock_client)
        assert published["status"] == "running"
        assert published["seed"] == 777
        assert published["readyFlags"] == {"user-bob": True, "user-alice": True}

    async def test_ready_uses_presence_roster_for_autostart(self):
        """Roster can come from party presence even when readyFlags has 1 entry."""
        state = _waiting_state()
        state["readyFlags"] = {"user-bob": True}
        mock_client = _make_async_redis(get_return=state)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            with patch("main._generate_seed", return_value=5):
                result = await main.execute_cell(
                    {"action": "ready", "roomId": "room-1", "participants": _presence(["user-alice", "user-bob"])},
                    user_id="user-alice",
                )

        assert result["output"]["status"] == "running"

    async def test_ready_waits_with_one_player(self):
        """Single player ready → still waiting (needs ≥2)."""
        state = _waiting_state()
        mock_client = _make_async_redis(get_return=state)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "ready", "roomId": "room-1"}, user_id="user-alice")

        assert result["success"] is True
        assert result["output"]["status"] == "waiting"
        # No start → exactly one publish (the ready snapshot).
        assert mock_client.publish.call_count == 1

    async def test_ready_ghost_does_not_autostart(self):
        """A player who left (pruned from presence) keeps a stale ready flag —
        the roster must come from presence ONLY (not readyFlags) so the ghost
        never pulls the remaining player into a 1v1."""
        state = _waiting_state()
        state["readyFlags"] = {"user-alice": True}  # alice left the room
        # Presence contains ONLY bob (alice was pruned by the heartbeat).
        mock_client = _make_async_redis(get_return=state)
        mock_client.get.return_value = json.dumps(_presence(["user-bob"]))

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "ready", "roomId": "room-1"}, user_id="user-bob")

        assert result["success"] is True
        assert result["output"]["status"] == "waiting"
        assert mock_client.publish.call_count == 1  # ready snapshot only

    async def test_ready_three_player_room_caps_match_to_two(self):
        """A 3-player room starts a 1v1 between the FIRST TWO ready players;
        the third is a spectator and is NOT in the match state."""
        state = _waiting_state()
        state["readyFlags"] = {"user-alice": True, "user-bob": True, "user-carol": True}
        mock_client = _make_async_redis(get_return=state)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            with patch("main._generate_seed", return_value=11):
                result = await main.execute_cell(
                    {"action": "ready", "roomId": "room-1", "participants": _presence(["user-alice", "user-bob", "user-carol"])},
                    user_id="user-alice",
                )

        assert result["output"]["status"] == "running"
        published = _published_state(mock_client)
        assert list(published["scores"].keys()) == ["user-alice", "user-bob"]
        assert "user-carol" not in published["scores"]
        assert list(published["readyFlags"].keys()) == ["user-alice", "user-bob"]

    async def test_ready_rejects_empty_room_id(self):
        result = await main.execute_cell({"action": "ready", "roomId": ""})
        assert result["success"] is False
        assert "roomid" in result["error"].lower()

    async def test_ready_rejects_unsafe_room_id(self):
        result = await main.execute_cell({"action": "ready", "roomId": "room; DROP;"})
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# start_game
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestStartGame:

    async def test_start_game_issues_seed_and_resets_state(self):
        state = _waiting_state()
        state["readyFlags"] = {"user-alice": True, "user-bob": True}
        mock_client = _make_async_redis(get_return=state)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            with patch("main._generate_seed", return_value=4242):
                result = await main.execute_cell(
                    {"action": "start_game", "roomId": "room-1", "participants": _presence(["user-alice", "user-bob"])},
                    user_id="user-alice",
                )

        assert result["success"] is True
        assert result["output"]["status"] == "running"
        assert result["output"]["seed"] == 4242

        published = _published_state(mock_client)
        assert published["round"] == 1
        assert published["scores"] == {"user-alice": 0, "user-bob": 0}
        assert published["garbagePending"] == {"user-alice": 0, "user-bob": 0}

    async def test_start_game_rejects_less_than_two_players(self):
        mock_client = _make_async_redis(get_return=_waiting_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "start_game", "roomId": "room-1", "participants": [_presence(["user-alice"])[0]]},
                user_id="user-alice",
            )

        assert result["success"] is False
        assert "at least 2 players" in result["error"]

    async def test_start_game_rejects_when_not_all_ready(self):
        state = _waiting_state()
        state["readyFlags"] = {"user-alice": True}  # bob not ready
        mock_client = _make_async_redis(get_return=state)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "start_game", "roomId": "room-1", "participants": _presence(["user-alice", "user-bob"])},
                user_id="user-alice",
            )

        assert result["success"] is False
        assert "not all players are ready" in result["error"]

    async def test_start_game_rejects_when_already_running(self):
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "start_game", "roomId": "room-1"}, user_id="user-alice")

        assert result["success"] is False
        assert "already running" in result["error"]

    async def test_start_game_allows_rematch_after_game_over(self):
        """Re-match: a game_over state starts directly without ready clicks."""
        state = _running_state()
        state["status"] = "game_over"
        state["gameOver"] = {"winnerId": "user-bob", "reason": "top-out"}
        state["readyFlags"] = {"user-alice": False, "user-bob": False}
        mock_client = _make_async_redis(get_return=state)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            with patch("main._generate_seed", return_value=999):
                result = await main.execute_cell(
                    {"action": "start_game", "roomId": "room-1", "participants": _presence(["user-alice", "user-bob"])},
                    user_id="user-alice",
                )

        assert result["success"] is True
        assert result["output"]["status"] == "running"
        assert result["output"]["seed"] == 999
        # Round incremented from 1 → 2 on the re-match.
        assert _published_state(mock_client)["round"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# submit_garbage
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestSubmitGarbage:

    async def test_submit_garbage_accumulates_on_target(self):
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "submit_garbage", "roomId": "room-1", "amount": 6, "targetId": "user-bob"},
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["garbagePending"]["user-bob"] == 6
        assert _published_state(mock_client)["garbagePending"]["user-bob"] == 6

    async def test_submit_garbage_derives_opponent_when_no_target(self):
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "submit_garbage", "roomId": "room-1", "amount": 3},
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["target"] == "user-bob"

    async def test_submit_garbage_rejects_invalid_amount(self):
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "submit_garbage", "roomId": "room-1", "amount": -5, "targetId": "user-bob"},
                user_id="user-alice",
            )

        assert result["success"] is False
        assert "amount" in result["error"]

    async def test_submit_garbage_clamps_large_amount(self):
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "submit_garbage", "roomId": "room-1", "amount": 5000, "targetId": "user-bob"},
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["amount"] == main.MAX_GARBAGE

    async def test_submit_garbage_rejects_self_target(self):
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "submit_garbage", "roomId": "room-1", "amount": 3, "targetId": "user-alice"},
                user_id="user-alice",
            )

        assert result["success"] is False
        assert "target" in result["error"]

    async def test_submit_garbage_rejects_when_not_running(self):
        mock_client = _make_async_redis(get_return=_waiting_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "submit_garbage", "roomId": "room-1", "amount": 3, "targetId": "user-bob"},
                user_id="user-alice",
            )

        assert result["success"] is False
        assert "not running" in result["error"]

    async def test_submit_garbage_rejects_outsider(self):
        """An outsider with the roomId cannot dump garbage on a match player."""
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "submit_garbage", "roomId": "room-1", "amount": 3, "targetId": "user-alice"},
                user_id="user-mallory",
            )

        assert result["success"] is False
        assert "match players" in result["error"]


# ─────────────────────────────────────────────────────────────────────────────
# piece_locked
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestPieceLocked:

    async def test_piece_locked_records_grid(self):
        grid = _grid(3)
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "piece_locked", "roomId": "room-1", "grid": grid, "score": 120},
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["grids"]["user-alice"] == grid
        assert _published_state(mock_client)["grids"]["user-alice"] == grid
        assert _published_state(mock_client)["scores"]["user-alice"] == 120

    async def test_piece_locked_rejects_invalid_grid(self):
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "piece_locked", "roomId": "room-1", "grid": [9] * 72, "score": 0},
                user_id="user-alice",
            )

        assert result["success"] is False
        assert "grid" in result["error"]

    async def test_piece_locked_rejects_wrong_length(self):
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "piece_locked", "roomId": "room-1", "grid": [1, 2, 3], "score": 0},
                user_id="user-alice",
            )

        assert result["success"] is False

    async def test_piece_locked_rejects_when_not_running(self):
        mock_client = _make_async_redis(get_return=_waiting_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "piece_locked", "roomId": "room-1", "grid": _grid(), "score": 0},
                user_id="user-alice",
            )

        assert result["success"] is False

    async def test_piece_locked_rejects_outsider(self):
        """An outsider cannot inject a grid/score into a running match."""
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "piece_locked", "roomId": "room-1", "grid": _grid(), "score": 0},
                user_id="user-mallory",
            )

        assert result["success"] is False
        assert "match players" in result["error"]


# ─────────────────────────────────────────────────────────────────────────────
# game_over
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestGameOver:

    async def test_game_over_arbitrates_opponent_as_winner(self):
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell(
                {"action": "game_over", "roomId": "room-1", "reason": "top-out"},
                user_id="user-alice",
            )

        assert result["success"] is True
        assert result["output"]["gameOver"]["winnerId"] == "user-bob"
        assert result["output"]["gameOver"]["reason"] == "top-out"

        published = _published_state(mock_client)
        assert published["status"] == "game_over"
        assert published["gameOver"]["winnerId"] == "user-bob"

    async def test_game_over_is_idempotent_when_already_over(self):
        state = _running_state()
        state["status"] = "game_over"
        state["gameOver"] = {"winnerId": "user-bob", "reason": "top-out"}
        mock_client = _make_async_redis(get_return=state)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "game_over", "roomId": "room-1"}, user_id="user-alice")

        assert result["success"] is True
        assert result["output"]["gameOver"]["winnerId"] == "user-bob"
        # No new publish when already over.
        assert mock_client.publish.call_count == 0

    async def test_game_over_resets_ready_flags(self):
        """A finished match clears ready flags so a stale ready never
        auto-starts the next match."""
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "game_over", "roomId": "room-1"}, user_id="user-alice")

        published = _published_state(mock_client)
        assert published["readyFlags"] == {"user-alice": False, "user-bob": False}

    async def test_game_over_rejects_outsider(self):
        """An outsider with the roomId cannot end a running match or force a
        winner."""
        mock_client = _make_async_redis(get_return=_running_state())

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "game_over", "roomId": "room-1"}, user_id="user-mallory")

        assert result["success"] is False
        assert "match players" in result["error"]
        # The running match was NOT mutated.
        assert mock_client.publish.call_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# snapshot_request
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestSnapshotRequest:

    async def test_snapshot_request_publishes_and_returns_hydration_body(self):
        state = _running_state()
        mock_client = _make_async_redis(get_return=state)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "snapshot_request", "roomId": "room-1"}, user_id="user-alice")

        assert result["success"] is True
        assert result["output"]["participantId"] == "user-alice"
        assert result["output"]["state"]["status"] == "running"
        assert result["output"]["state"]["seed"] == 12345

        channel, raw = _last_publish(mock_client)
        assert channel == "puyo:game:room-1"
        assert json.loads(raw)["type"] == "snapshot"


# ─────────────────────────────────────────────────────────────────────────────
# Validation branches (empty / unsafe roomId for every action)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestValidationBranches:

    async def test_start_game_rejects_empty_room_id(self):
        result = await main.execute_cell({"action": "start_game", "roomId": ""})
        assert result["success"] is False
        assert "roomid" in result["error"].lower()

    async def test_submit_garbage_rejects_unsafe_room_id(self):
        result = await main.execute_cell({"action": "submit_garbage", "roomId": "bad;room"})
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()

    async def test_piece_locked_rejects_empty_room_id(self):
        result = await main.execute_cell({"action": "piece_locked", "roomId": ""})
        assert result["success"] is False

    async def test_game_over_rejects_unsafe_room_id(self):
        result = await main.execute_cell({"action": "game_over", "roomId": "bad;room"})
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()

    async def test_snapshot_request_rejects_empty_room_id(self):
        result = await main.execute_cell({"action": "snapshot_request", "roomId": ""})
        assert result["success"] is False
        assert "roomid" in result["error"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Lock / Redis failure tolerance / edge cases
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestRobustness:

    async def test_room_lock_busy_rejects(self):
        with patch("main._acquire_room_lock", new=AsyncMock(return_value=False)):
            result = await main.execute_cell({"action": "ready", "roomId": "room-1"})
        assert result["success"] is False
        assert "busy" in result["error"]

    async def test_redis_read_failure_degrades_gracefully(self):
        mock_client = _make_async_redis()
        mock_client.get = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "snapshot_request", "roomId": "room-1"}, user_id="user-alice")

        assert result["success"] is True
        assert result["output"]["state"]["status"] == "waiting"

    async def test_redis_write_failure_does_not_crash(self):
        mock_client = _make_async_redis(get_return=_waiting_state())
        mock_client.set = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "ready", "roomId": "room-1"}, user_id="user-alice")

        assert result["success"] is True

    async def test_publish_failure_does_not_crash(self):
        mock_client = _make_async_redis(get_return=_waiting_state())
        mock_client.publish = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "ready", "roomId": "room-1"}, user_id="user-alice")

        assert result["success"] is True

    async def test_lock_acquire_failure_fails_open(self):
        """Redis failure on the lock key → _acquire_room_lock fails open."""
        mock_client = _make_async_redis(get_return=_waiting_state())

        def fake_set(key, *args, **kwargs):
            if key == main._lock_key("room-1"):
                raise RuntimeError("redis down")
            return True

        mock_client.set = AsyncMock(side_effect=fake_set)

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "ready", "roomId": "room-1"}, user_id="user-alice")

        # Fail-open: lock problems never block the game.
        assert result["success"] is True

    async def test_lock_release_failure_does_not_crash(self):
        mock_client = _make_async_redis(get_return=_waiting_state())
        mock_client.delete = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch("main._get_async_redis_client", new=AsyncMock(return_value=mock_client)):
            result = await main.execute_cell({"action": "ready", "roomId": "room-1"}, user_id="user-alice")

        assert result["success"] is True

    async def test_generate_seed_returns_32bit_int(self):
        for _ in range(20):
            seed = main._generate_seed()
            assert isinstance(seed, int)
            assert 0 <= seed <= 0xFFFFFFFF

    async def test_unknown_action_returns_error(self):
        result = await main.execute_cell({"action": "fly_to_the_moon", "roomId": "room-1"})
        assert result["success"] is False
        assert "fly_to_the_moon" in result["error"]

    async def test_missing_action_returns_error(self):
        result = await main.execute_cell({"roomId": "room-1"})
        assert result["success"] is False

    async def test_keys_are_isolated_per_room(self):
        assert main._channel("a") == "puyo:game:a"
        assert main._channel("b") == "puyo:game:b"
        assert main._snapshot_key("a") != main._snapshot_key("b")
