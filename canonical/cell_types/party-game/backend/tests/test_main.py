"""Tests for party-game backend (main.py + word_bank.py).  Target >=90% lines.

Redis is faked with an in-memory client patched over ``main._get_async_redis_client``.
"""

import json
import random
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

cell_root = Path(__file__).parent.parent
sys.path.insert(0, str(cell_root / "scripts"))
REPO_ROOT = Path(__file__).resolve().parents[6]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main  # noqa: E402
import word_bank  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.publishes = []

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None, px=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def delete(self, key):
        return self.store.pop(key, None) is not None

    async def publish(self, channel, message):
        self.publishes.append((channel, message))
        return 1

    async def aclose(self):
        pass


@pytest.fixture
def redis():
    return FakeRedis()


@pytest.fixture
def backend(redis):
    with patch("main._get_async_redis_client", new=AsyncMock(return_value=redis)):
        yield main


def _messages(redis, channel):
    return [json.loads(m) for (ch, m) in redis.publishes if ch == channel]


def _seed_presence(redis, room, players):
    redis.store[f"calls:presence:{room}"] = json.dumps(players)


def _player(pid, name, session=None):
    return {"participantId": pid, "sessionId": session or pid, "displayName": name, "tracks": [], "isMuted": False}


async def _started_game(backend, redis, room="room1"):
    _seed_presence(redis, room, [_player("u1", "Alice"), _player("u2", "Bob")])
    with patch.object(backend, "pick_word_with_llm", return_value=("animals", "penguin")):
        return await backend.execute_cell({"action": "start_game", "roomId": room}, user_id="u1")


# ── presence ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_join_game_upserts_presence_and_publishes(backend, redis):
    result = await backend.execute_cell({"action": "join_game", "roomId": "room1", "sessionId": "s-a", "displayName": "Alice"}, user_id="u1")
    assert result["success"] is True and result["output"]["count"] == 1
    snap = _messages(redis, "calls:room:room1")[-1]
    assert snap["type"] == "snapshot"
    assert snap["payload"]["state"][0]["participantId"] == "u1"
    assert snap["payload"]["state"][0]["sessionId"] == "s-a"


@pytest.mark.asyncio
async def test_join_game_rejects_bad_room(backend, redis):
    result = await backend.execute_cell({"action": "join_game", "roomId": "bad room!"})
    assert result["success"] is False and "invalid characters" in result["error"]


@pytest.mark.asyncio
async def test_join_game_requires_room(backend, redis):
    result = await backend.execute_cell({"action": "join_game"})
    assert result["success"] is False and "roomId is required" in result["error"]


@pytest.mark.asyncio
async def test_join_game_replaces_same_session(backend, redis):
    await backend.execute_cell({"action": "join_game", "roomId": "room1", "sessionId": "s-a", "displayName": "Alice"}, user_id="u1")
    result = await backend.execute_cell({"action": "join_game", "roomId": "room1", "sessionId": "s-a", "displayName": "Alice Renamed"}, user_id="u1")
    assert result["output"]["count"] == 1
    assert result["output"]["participants"][0]["displayName"] == "Alice Renamed"


@pytest.mark.asyncio
async def test_join_game_uses_current_user_name(backend, redis):
    current_user = MagicMock()
    current_user.id = "u1"
    current_user.name = "Alice Von Auth"
    result = await backend.execute_cell({"action": "join_game", "roomId": "room1", "sessionId": "s-a", "_current_user": current_user}, user_id="u1")
    assert result["output"]["participants"][0]["displayName"] == "Alice Von Auth"


@pytest.mark.asyncio
async def test_leave_game_removes_by_session(backend, redis):
    _seed_presence(redis, "room1", [_player("u1", "Alice", "s-a"), _player("u2", "Bob", "s-b")])
    result = await backend.execute_cell({"action": "leave_game", "roomId": "room1", "sessionId": "s-a"}, user_id="u1")
    assert result["output"]["count"] == 1 and result["output"]["participants"][0]["participantId"] == "u2"


@pytest.mark.asyncio
async def test_leave_game_by_participant_and_bad_room(backend, redis):
    _seed_presence(redis, "room1", [_player("u1", "Alice", "s-a"), _player("u2", "Bob", "s-b")])
    result = await backend.execute_cell({"action": "leave_game", "roomId": "room1"}, user_id="u2")
    assert result["output"]["count"] == 1
    bad = await backend.execute_cell({"action": "leave_game", "roomId": "bad room!"})
    assert bad["success"] is False


# ── start / rounds ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_game_rejects_single_player(backend, redis):
    _seed_presence(redis, "room1", [_player("u1", "Alice")])
    result = await backend.execute_cell({"action": "start_game", "roomId": "room1"}, user_id="u1")
    assert result["success"] is False and "at least 2 players" in result["error"]


@pytest.mark.asyncio
async def test_start_game_runs_round_one_and_hides_word(backend, redis):
    result = await _started_game(backend, redis)
    assert result["success"] is True and result["output"]["round"] == 1
    assert result["output"]["drawerId"] == "u1"
    assert json.loads(redis.store["game:word:room1"]) == "penguin"
    published = _messages(redis, "game:room:room1:state")[-1]["payload"]["state"]
    assert published["phase"] == "draw" and "word" not in published and "penguin" not in json.dumps(published)
    assert _messages(redis, "game:room:room1:strokes")[-1]["payload"]["state"] == []
    assert _messages(redis, "game:room:room1:guesses")[-1]["payload"]["operations"][0]["value"]["type"] == "system"


@pytest.mark.asyncio
async def test_start_round_round_robin_and_strokes_reset(backend, redis):
    await _started_game(backend, redis)
    with patch.object(backend, "pick_word_with_llm", return_value=("animals", "lion")):
        result = await backend.execute_cell({"action": "start_round", "roomId": "room1"}, user_id="u1")
    assert result["output"]["round"] == 2 and result["output"]["drawerId"] == "u2"
    assert json.loads(redis.store["game:word:room1"]) == "lion"


@pytest.mark.asyncio
async def test_start_round_bad_room(backend, redis):
    assert (await backend.execute_cell({"action": "start_round", "roomId": "bad room!"}))["success"] is False


@pytest.mark.asyncio
async def test_next_round_bad_room(backend, redis):
    assert (await backend.execute_cell({"action": "next_round", "roomId": "bad room!"}))["success"] is False


@pytest.mark.asyncio
async def test_start_round_before_game(backend, redis):
    result = await backend.execute_cell({"action": "start_round", "roomId": "room1"}, user_id="u1")
    assert result["success"] is False and "start the game first" in result["error"]


@pytest.mark.asyncio
async def test_start_round_finished_rejected(backend, redis):
    await _started_game(backend, redis)
    await backend.execute_cell({"action": "end_game", "roomId": "room1"}, user_id="u1")
    result = await backend.execute_cell({"action": "start_round", "roomId": "room1"}, user_id="u1")
    # After end_game drawerId is None → the drawer gate blocks (start_game restarts).
    assert result["success"] is False and "only the drawer" in result["error"]


@pytest.mark.asyncio
async def test_start_game_bad_room_and_fallback_players(backend, redis):
    bad = await backend.execute_cell({"action": "start_game", "roomId": "bad room!"})
    assert bad["success"] is False
    result = await backend.execute_cell({"action": "start_game", "roomId": "room1", "participants": [_player("u1", "Alice"), _player("u2", "Bob")]}, user_id="u1")
    assert result["success"] is True and result["output"]["drawerId"] == "u1"


@pytest.mark.asyncio
async def test_next_round_reveals_word_and_advances(backend, redis):
    await _started_game(backend, redis)
    with patch.object(backend, "pick_word_with_llm", return_value=("animals", "lion")):
        result = await backend.execute_cell({"action": "next_round", "roomId": "room1"}, user_id="u1")
    assert result["output"]["round"] == 2
    revealed = [m for m in _messages(redis, "game:room:room1:guesses") if m["type"] == "patch"]
    assert any("The word was 'penguin'" in m["payload"]["operations"][0]["value"]["text"] for m in revealed)


@pytest.mark.asyncio
async def test_next_round_ends_game_when_exhausted(backend, redis):
    _seed_presence(redis, "room1", [_player("u1", "Alice"), _player("u2", "Bob")])
    with patch.object(backend, "pick_word_with_llm", return_value=("animals", "penguin")):
        await backend.execute_cell({"action": "start_game", "roomId": "room1", "totalRounds": 1}, user_id="u1")
        result = await backend.execute_cell({"action": "next_round", "roomId": "room1"}, user_id="u1")
    assert result["output"]["phase"] == "finished"
    assert _messages(redis, "game:room:room1:state")[-1]["payload"]["state"]["phase"] == "finished"


@pytest.mark.asyncio
async def test_next_round_before_game(backend, redis):
    result = await backend.execute_cell({"action": "next_round", "roomId": "room1"}, user_id="u1")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_end_game_finishes(backend, redis):
    await _started_game(backend, redis)
    result = await backend.execute_cell({"action": "end_game", "roomId": "room1"}, user_id="u1")
    assert result["output"]["phase"] == "finished"


@pytest.mark.asyncio
async def test_end_game_before_start_and_bad_room(backend, redis):
    result = await backend.execute_cell({"action": "end_game", "roomId": "room1"}, user_id="u1")
    assert result["success"] is False and "start the game first" in result["error"]
    assert (await backend.execute_cell({"action": "end_game", "roomId": "bad room!"}))["success"] is False


@pytest.mark.asyncio
async def test_run_next_round_no_players(backend, redis):
    result = await backend._run_next_round("room1", {"players": [], "round": 0, "totalRounds": 1}, "u1")
    assert result["success"] is False


# ── get_secret / guess ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_secret_only_for_drawer(backend, redis):
    await _started_game(backend, redis)
    ok = await backend.execute_cell({"action": "get_secret", "roomId": "room1"}, user_id="u1")
    assert ok["output"]["secretWord"] == "penguin"
    denied = await backend.execute_cell({"action": "get_secret", "roomId": "room1"}, user_id="u2")
    assert denied["success"] is False and "only the drawer" in denied["error"]


@pytest.mark.asyncio
async def test_get_secret_not_spoofable_via_participant_id(backend, redis):
    """OWASP A07: _caller_id trusts the authenticated user_id, not the client
    participantId.  A guesser spoofing participantId=drawer is still denied."""
    await _started_game(backend, redis)
    # u2 (guesser) tries to spoof the drawer's participantId u1 → denied.
    denied = await backend.execute_cell({"action": "get_secret", "roomId": "room1", "participantId": "u1"}, user_id="u2")
    assert denied["success"] is False and "only the drawer" in denied["error"]


@pytest.mark.asyncio
async def test_get_secret_guards(backend, redis):
    assert (await backend.execute_cell({"action": "get_secret", "roomId": "bad room!"}))["success"] is False
    await _started_game(backend, redis)
    redis.store["game:word:room1"] = "null"
    no_word = await backend.execute_cell({"action": "get_secret", "roomId": "room1"}, user_id="u1")
    assert no_word["success"] is False and "no active round" in no_word["error"]


@pytest.mark.asyncio
async def test_submit_guess_correct_scores_and_reveals(backend, redis):
    await _started_game(backend, redis)
    result = await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "PENGUIN!"}, user_id="u2")
    assert result["output"]["correct"] is True and result["output"]["points"] == 100
    state = _messages(redis, "game:room:room1:state")[-1]["payload"]["state"]
    assert state["phase"] == "reveal" and state["scores"]["u2"] == 100 and state["roundWinners"] == ["u2"]


@pytest.mark.asyncio
async def test_submit_guess_contains_match(backend, redis):
    await _started_game(backend, redis)
    result = await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "i love penguins"}, user_id="u2")
    assert result["output"]["correct"] is True


@pytest.mark.asyncio
async def test_submit_guess_wrong_then_hint_after_three(backend, redis):
    await _started_game(backend, redis)
    for i in range(3):
        result = await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": f"wrong{i}"}, user_id="u2")
        assert result["output"]["correct"] is False
        assert result["output"]["hint"] is None if i < 2 else result["output"]["hint"] is not None
    state = _messages(redis, "game:room:room1:state")[-1]["payload"]["state"]
    assert state["wrongCount"] == 3 and state["hintCount"] == 1 and state["phase"] == "guess"
    assert _messages(redis, "game:room:room1:guesses")[-1]["payload"]["operations"][0]["value"]["type"] == "hint"


@pytest.mark.asyncio
async def test_submit_guess_drawer_does_not_guess(backend, redis):
    await _started_game(backend, redis)
    result = await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "penguin"}, user_id="u1")
    assert result["output"]["status"] == "drawer"


@pytest.mark.asyncio
async def test_submit_guess_requires_text_and_round(backend, redis):
    no_text = await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "  "}, user_id="u1")
    assert no_text["success"] is False and "guess is required" in no_text["error"]
    no_round = await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "hi"}, user_id="u1")
    assert no_round["success"] is False


@pytest.mark.asyncio
async def test_wrong_guess_after_reveal_does_not_regress_phase(backend, redis):
    await _started_game(backend, redis)
    await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "penguin"}, user_id="u2")
    assert _messages(redis, "game:room:room1:state")[-1]["payload"]["state"]["phase"] == "reveal"
    # A later wrong guess must NOT regress the resolved round back to 'guess'.
    await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "wrong"}, user_id="u2")
    state = _messages(redis, "game:room:room1:state")[-1]["payload"]["state"]
    assert state["phase"] == "reveal"


@pytest.mark.asyncio
async def test_submit_guess_double_correct_no_double_score(backend, redis):
    await _started_game(backend, redis)
    await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "penguin"}, user_id="u2")
    again = await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "penguin"}, user_id="u2")
    assert again["output"]["correct"] is True and again["output"]["already"] is True


@pytest.mark.asyncio
async def test_submit_guess_guards(backend, redis):
    assert (await backend.execute_cell({"action": "submit_guess", "roomId": "bad room!", "guess": "x"}, user_id="u1"))["success"] is False
    await _started_game(backend, redis)
    redis.store["game:word:room1"] = "null"
    no_word = await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "penguin"}, user_id="u2")
    assert no_word["success"] is False and "no secret word" in no_word["error"]


@pytest.mark.asyncio
async def test_submit_guess_unknown_player_display_name(backend, redis):
    await _started_game(backend, redis)
    result = await backend.execute_cell({"action": "submit_guess", "roomId": "room1", "guess": "wrong", "displayName": "Carol"}, user_id="u3")
    assert result["success"] is True and result["output"]["correct"] is False


# ── hint / strokes / snapshot ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hint_action_publishes(backend, redis):
    await _started_game(backend, redis)
    result = await backend.execute_cell({"action": "hint", "roomId": "room1"}, user_id="u1")
    assert result["output"]["hintCount"] == 1
    assert _messages(redis, "game:room:room1:guesses")[-1]["payload"]["operations"][0]["value"]["type"] == "hint"


@pytest.mark.asyncio
async def test_hint_gated_to_drawer(backend, redis):
    await _started_game(backend, redis)
    denied = await backend.execute_cell({"action": "hint", "roomId": "room1"}, user_id="u2")
    assert denied["success"] is False and "only the drawer" in denied["error"]


@pytest.mark.asyncio
async def test_hint_requires_active_round(backend, redis):
    _seed_presence(redis, "room1", [_player("u1", "Alice"), _player("u2", "Bob")])
    result = await backend.execute_cell({"action": "hint", "roomId": "room1"}, user_id="u1")
    assert result["success"] is False and "start the game first" in result["error"]


@pytest.mark.asyncio
async def test_append_stroke_publishes_patch(backend, redis):
    await _started_game(backend, redis)
    stroke = {"tool": "pen", "color": "#000", "width": 2, "points": [[0, 0], [1, 1]]}
    result = await backend.execute_cell({"action": "append_stroke", "roomId": "room1", "stroke": stroke}, user_id="u1")
    assert result["output"]["count"] == 1
    patch_msg = _messages(redis, "game:room:room1:strokes")[-1]
    assert patch_msg["type"] == "patch" and patch_msg["payload"]["operations"][0]["path"] == "/-"
    assert json.loads(redis.store["game:strokes:room1"])[0]["id"]


@pytest.mark.asyncio
async def test_append_stroke_rejects_invalid(backend, redis):
    await _started_game(backend, redis)
    bad = await backend.execute_cell({"action": "append_stroke", "roomId": "room1", "stroke": "nope"}, user_id="u1")
    assert bad["success"] is False and "stroke is required" in bad["error"]


@pytest.mark.asyncio
async def test_append_stroke_requires_active_round(backend, redis):
    _seed_presence(redis, "room1", [_player("u1", "Alice"), _player("u2", "Bob")])
    no_round = await backend.execute_cell({"action": "append_stroke", "roomId": "room1", "stroke": {"points": []}}, user_id="u1")
    assert no_round["success"] is False and "start the game first" in no_round["error"]


@pytest.mark.asyncio
async def test_clear_canvas_publishes_empty_snapshot(backend, redis):
    await _started_game(backend, redis)
    result = await backend.execute_cell({"action": "clear_canvas", "roomId": "room1"}, user_id="u1")
    assert result["success"] is True
    assert _messages(redis, "game:room:room1:strokes")[-1]["payload"]["state"] == []


@pytest.mark.asyncio
async def test_drawer_gates_block_guessers(backend, redis):
    """OWASP A01: next_round/end_game/append_stroke/clear_canvas are drawer-only."""
    await _started_game(backend, redis)
    for action in ("next_round", "end_game", "append_stroke", "clear_canvas"):
        payload = {"action": action, "roomId": "room1"}
        if action == "append_stroke":
            payload["stroke"] = {"points": [[0, 0]]}
        result = await backend.execute_cell(payload, user_id="u2")
        assert result["success"] is False and "only the drawer" in result["error"], action


@pytest.mark.asyncio
async def test_snapshot_request_publishes_all_branches(backend, redis):
    await _started_game(backend, redis)
    result = await backend.execute_cell({"action": "snapshot_request", "roomId": "room1"}, user_id="u1")
    assert result["success"] is True and result["output"]["secretWord"] == "penguin"
    assert any(m["type"] == "snapshot" for m in _messages(redis, "game:room:room1:state"))
    assert any(m["type"] == "snapshot" for m in _messages(redis, "game:room:room1:strokes"))
    assert any(m["type"] == "snapshot" for m in _messages(redis, "game:room:room1:guesses"))


@pytest.mark.asyncio
async def test_snapshot_request_non_drawer_no_word(backend, redis):
    await _started_game(backend, redis)
    result = await backend.execute_cell({"action": "snapshot_request", "roomId": "room1"}, user_id="u2")
    assert result["success"] is True and "secretWord" not in result["output"]


@pytest.mark.asyncio
async def test_room_lock_fail_open_and_release_errors(backend, redis):
    redis.set = AsyncMock(side_effect=RuntimeError("down"))
    assert await backend._acquire_room_lock("room1") is True  # fail-open
    redis.delete = AsyncMock(side_effect=RuntimeError("down"))
    await backend._release_room_lock("room1")  # swallowed


@pytest.mark.asyncio
async def test_locked_action_returns_busy_when_lock_held(backend, redis):
    await _started_game(backend, redis)
    redis.store["game:lock:room1"] = "1"
    result = await backend.execute_cell({"action": "next_round", "roomId": "room1"}, user_id="u1")
    assert result["success"] is False and "busy" in result["error"]


@pytest.mark.asyncio
async def test_hint_no_word(backend, redis):
    await _started_game(backend, redis)
    redis.store["game:word:room1"] = "null"
    result = await backend.execute_cell({"action": "hint", "roomId": "room1"}, user_id="u1")
    assert result["success"] is False and "no active round" in result["error"]


@pytest.mark.asyncio
async def test_action_bad_room_guards(backend, redis):
    for action in ("append_stroke", "clear_canvas", "snapshot_request", "hint"):
        assert (await backend.execute_cell({"action": action, "roomId": "bad room!"}))["success"] is False


@pytest.mark.asyncio
async def test_unknown_action(backend, redis):
    result = await backend.execute_cell({"action": "nope", "roomId": "room1"})
    assert result["success"] is False and "Unknown action" in result["error"]


# ── Redis internals ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redis_client_builds_from_l1_config(monkeypatch):
    import redis.asyncio as aioredis

    captured, created = {}, []

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            created.append(self)

    monkeypatch.setattr(aioredis, "Redis", FakeClient)
    import backend.app.config.database as dbconfig

    monkeypatch.setattr(dbconfig, "REDIS_L1_PASSWORD", "s3cret")
    client = main._get_async_redis_client()
    assert client in created
    assert captured["decode_responses"] is True and captured["password"] == "s3cret" and captured["db"] >= 0


@pytest.mark.asyncio
async def test_redis_helpers_swallow_errors(backend, redis):
    redis.get = AsyncMock(side_effect=RuntimeError("down"))
    assert await backend._redis_get_json("k", []) == []
    redis.set = AsyncMock(side_effect=RuntimeError("down"))
    await backend._redis_set_json("k", {"a": 1})
    redis.publish = AsyncMock(side_effect=RuntimeError("down"))
    await backend._publish("ch", {"a": 1})


# ── word_bank ────────────────────────────────────────────────────────────────


def test_normalize_text_strips_accents_case_and_punctuation():
    assert word_bank.normalize_text("  PÉ-NGUIM!  ") == "penguim"


def test_guess_matches_exact_contains_and_miss():
    assert word_bank.guess_matches("PENGUIN", "penguin") is True
    assert word_bank.guess_matches("love penguin", "penguin") is True
    assert word_bank.guess_matches("cat", "penguin") is False
    assert word_bank.guess_matches("", "penguin") is False


def test_guess_matches_does_not_match_short_prefix():
    # One-directional: a short guess being a prefix/contained of the secret
    # word must NOT match (review finding — 'key' vs 'monkey', 'ele' vs 'elephant').
    assert word_bank.guess_matches("key", "monkey") is False
    assert word_bank.guess_matches("ele", "elephant") is False
    assert word_bank.guess_matches("pen", "penguin") is False


def test_pick_word_respects_category_and_rng():
    rng = random.Random(42)
    cat, word = word_bank.pick_word("animals", rng)
    assert cat == "animals" and word in word_bank.WORD_BANK["animals"]


def test_pick_word_random_category():
    cat, word = word_bank.pick_word()
    assert cat in word_bank.DEFAULT_CATEGORIES and word in word_bank.WORD_BANK[cat]


def test_pick_category_returns_valid():
    assert word_bank.pick_category() in word_bank.DEFAULT_CATEGORIES


def test_generate_hint_progressive():
    assert "7 letters" in word_bank.generate_hint("penguin", 1, "animals")
    assert "animals" in word_bank.generate_hint("penguin", 1, "animals")
    assert "P" in word_bank.generate_hint("penguin", 2)
    assert "P" in word_bank.generate_hint("penguin", 3) and "N" in word_bank.generate_hint("penguin", 3)


def test_generate_hint_4_and_fallback():
    assert "Mask" in word_bank.generate_hint("penguin", 4)
    assert "Keep guessing!" in word_bank.generate_hint("penguin", 5, None)


def test_word_length_hint():
    assert word_bank.word_length_hint("hi") == "_ _"


def test_pick_word_with_llm_falls_back_on_failure():
    with patch.object(word_bank, "_llm_pick_word", side_effect=Exception("network down")):
        cat, word = word_bank.pick_word_with_llm(base_url="http://x", model="m", timeout=0.01)
    assert word in word_bank.WORD_BANK[cat]


def test_pick_word_with_llm_uses_llm_answer():
    with patch.object(word_bank, "_llm_pick_word", return_value="penguin"):
        cat, word = word_bank.pick_word_with_llm(base_url="http://x", model="m", timeout=0.01)
    assert word == "penguin" and cat == "animals"


def test_pick_word_with_llm_rejects_garbage():
    with patch.object(word_bank, "_llm_pick_word", return_value="!!!nope123!!!"):
        cat, word = word_bank.pick_word_with_llm(base_url="http://x", model="m", timeout=0.01)
    assert word in word_bank.WORD_BANK[cat]


def test_sanitize_llm_word():
    assert word_bank._sanitize_llm_word("  'Rocket'! ", None) == "rocket"
    assert word_bank._sanitize_llm_word("123 !!!", None) is None
    assert word_bank._sanitize_llm_word("", None) is None
    assert word_bank._sanitize_llm_word(None, None) is None


def test_llm_pick_word_parses_response():
    class FakeResp:
        def __init__(self, text):
            self._text = text

        def read(self):
            return json.dumps({"response": self._text}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch.object(word_bank.urllib.request, "urlopen", return_value=FakeResp("A rocket")):
        assert word_bank._llm_pick_word("http://x", "m", 0.01, "objects") == "rocket"


def test_llm_pick_word_propagates_transport_errors():
    with patch.object(word_bank.urllib.request, "urlopen", side_effect=Exception("boom")):
        with pytest.raises(Exception):
            word_bank._llm_pick_word("http://x", "m", 0.01)


def test_nearest_category_is_none_outside_bank():
    # An LLM word outside the bank gets NO category (hint must not lie).
    assert word_bank._nearest_category("penguin") == "animals"
    assert word_bank._nearest_category("zzz-not-a-word") is None


def test_ollama_base_url_resolution(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    assert word_bank._ollama_base_url() == "http://ollama:11434"
    monkeypatch.delenv("OLLAMA_BASE_URL")
    monkeypatch.setenv("OLLAMA_HOST", "http://scareverse-ollama-raw:11434")
    assert word_bank._ollama_base_url() == "http://scareverse-ollama-raw:11434"
    monkeypatch.delenv("OLLAMA_HOST")
    assert word_bank._ollama_base_url() == "http://localhost:11434"


def test_ollama_base_url_falls_back_when_config_raises(monkeypatch):
    from backend.app.config import Config

    def boom():
        raise RuntimeError("config down")

    monkeypatch.setattr(Config, "ollama_base_url", staticmethod(boom))
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert word_bank._ollama_base_url() == "http://localhost:11434"
