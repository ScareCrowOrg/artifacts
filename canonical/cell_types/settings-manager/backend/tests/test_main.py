"""
Tests for Settings Manager Cell backend scripts.

Covers all CRUD actions: list, create, update, delete, history, rollback,
push_redis.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import importlib.util
import pytest

# Load the module directly to avoid hyphen-in-path import issues
_scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_scripts_dir))

from main import (  # noqa: E402
    execute_cell,
    _load_settings,
    _load_history,
    _save_settings,
    _coerce_value,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_settings(tmp_path, monkeypatch):
    """Provide a temporary settings.json and patch TENANT_NAME / HOME."""
    tenant_dir = tmp_path / ".scareverse" / "staging" / "settings"
    tenant_dir.mkdir(parents=True)
    settings_path = tenant_dir / "settings.json"
    data = {
        "settings": {
            "log_level": {
                "value": "INFO",
                "type": "string",
                "category": "logging",
                "last_updated": "2026-01-01T00:00:00+00:00",
                "created_by": "admin",
            },
            "max_workers": {
                "value": 4,
                "type": "number",
                "category": "performance",
                "last_updated": "2026-01-01T00:00:00+00:00",
                "created_by": "admin",
            },
        }
    }
    settings_path.write_text(json.dumps(data, indent=2))

    monkeypatch.setenv("TENANT_NAME", "staging")
    monkeypatch.setenv("HOME", str(tmp_path))
    return settings_path


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestListSettings:
    def test_list_returns_all_settings(self, tmp_settings):
        body, status = execute_cell("list", service="launcher")
        assert status == 200
        assert len(body["settings"]) == 2

    def test_list_includes_metadata(self, tmp_settings):
        body, _ = execute_cell("list", service="launcher")
        keys = {s["setting_key"] for s in body["settings"]}
        assert "log_level" in keys
        assert "max_workers" in keys

    def test_list_includes_type(self, tmp_settings):
        body, _ = execute_cell("list", service="launcher")
        log = next(s for s in body["settings"] if s["setting_key"] == "log_level")
        assert log["type"] == "string"
        assert log["category"] == "logging"

    def test_list_empty_settings(self, tmp_settings):
        _save_settings(str(tmp_settings), {"settings": {}})
        body, status = execute_cell("list", service="launcher")
        assert status == 200
        assert body["settings"] == []


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreateSetting:
    def test_create_string_success(self, tmp_settings):
        body, status = execute_cell(
            "create",
            payload={"setting_key": "app_name", "value": "ScareVerse", "type": "string"},
            service="launcher",
        )
        assert status == 201
        assert body["success"] is True

    def test_create_number_success(self, tmp_settings):
        body, status = execute_cell(
            "create",
            payload={"setting_key": "timeout", "value": "30", "type": "number"},
            service="launcher",
        )
        assert status == 201

    def test_create_boolean_success(self, tmp_settings):
        body, status = execute_cell(
            "create",
            payload={"setting_key": "debug_mode", "value": "true", "type": "boolean"},
            service="launcher",
        )
        assert status == 201

    def test_create_json_success(self, tmp_settings):
        body, status = execute_cell(
            "create",
            payload={"setting_key": "feature_flags", "value": '{"dark_mode": true}', "type": "json"},
            service="launcher",
        )
        assert status == 201

    def test_create_persisted(self, tmp_settings):
        execute_cell(
            "create",
            payload={"setting_key": "new_key", "value": "new_val"},
            service="launcher",
        )
        data = _load_settings(str(tmp_settings))
        assert "new_key" in data["settings"]

    def test_create_missing_key_returns_400(self, tmp_settings):
        body, status = execute_cell("create", payload={"value": "v"}, service="launcher")
        assert status == 400

    def test_create_missing_value_returns_400(self, tmp_settings):
        body, status = execute_cell("create", payload={"setting_key": "k"}, service="launcher")
        assert status == 400

    def test_create_duplicate_returns_409(self, tmp_settings):
        body, status = execute_cell(
            "create",
            payload={"setting_key": "log_level", "value": "DEBUG"},
            service="launcher",
        )
        assert status == 409

    def test_create_invalid_type_returns_400(self, tmp_settings):
        body, status = execute_cell(
            "create",
            payload={"setting_key": "k", "value": "v", "type": "bytes"},
            service="launcher",
        )
        assert status == 400

    def test_create_invalid_number_returns_422(self, tmp_settings):
        body, status = execute_cell(
            "create",
            payload={"setting_key": "bad_num", "value": "not-a-number", "type": "number"},
            service="launcher",
        )
        assert status == 422

    def test_create_appends_history(self, tmp_settings):
        history_path = str(tmp_settings).replace("settings.json", "settings_history.json")
        execute_cell(
            "create",
            payload={"setting_key": "new_key", "value": "v"},
            service="launcher",
        )
        entries = _load_history(history_path)
        assert any(e["action"] == "CREATE" and e["setting_key"] == "new_key" for e in entries)


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdateSetting:
    def test_update_success(self, tmp_settings):
        body, status = execute_cell(
            "update",
            payload={"setting_key": "log_level", "value": "DEBUG"},
            service="launcher",
        )
        assert status == 200
        assert body["success"] is True

    def test_update_persisted(self, tmp_settings):
        execute_cell(
            "update",
            payload={"setting_key": "log_level", "value": "DEBUG"},
            service="launcher",
        )
        data = _load_settings(str(tmp_settings))
        assert data["settings"]["log_level"]["value"] == "DEBUG"

    def test_update_missing_key_returns_400(self, tmp_settings):
        body, status = execute_cell("update", payload={"value": "x"}, service="launcher")
        assert status == 400

    def test_update_nonexistent_returns_404(self, tmp_settings):
        body, status = execute_cell(
            "update",
            payload={"setting_key": "ghost", "value": "x"},
            service="launcher",
        )
        assert status == 404

    def test_update_appends_history(self, tmp_settings):
        history_path = str(tmp_settings).replace("settings.json", "settings_history.json")
        execute_cell(
            "update",
            payload={"setting_key": "log_level", "value": "WARN"},
            service="launcher",
        )
        entries = _load_history(history_path)
        assert any(e["action"] == "UPDATE" and e["setting_key"] == "log_level" for e in entries)

    def test_update_stores_previous_value_in_history(self, tmp_settings):
        history_path = str(tmp_settings).replace("settings.json", "settings_history.json")
        execute_cell(
            "update",
            payload={"setting_key": "log_level", "value": "WARN"},
            service="launcher",
        )
        entries = _load_history(history_path)
        entry = next(e for e in entries if e["setting_key"] == "log_level")
        assert entry["previous_value"] == "INFO"
        assert entry["new_value"] == "WARN"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDeleteSetting:
    def test_delete_success(self, tmp_settings):
        body, status = execute_cell(
            "delete",
            payload={"setting_key": "log_level"},
            service="launcher",
        )
        assert status == 200
        assert body["success"] is True

    def test_delete_removes_setting(self, tmp_settings):
        execute_cell("delete", payload={"setting_key": "log_level"}, service="launcher")
        data = _load_settings(str(tmp_settings))
        assert "log_level" not in data["settings"]

    def test_delete_missing_key_returns_400(self, tmp_settings):
        body, status = execute_cell("delete", payload={}, service="launcher")
        assert status == 400

    def test_delete_nonexistent_returns_404(self, tmp_settings):
        body, status = execute_cell(
            "delete", payload={"setting_key": "ghost"}, service="launcher"
        )
        assert status == 404

    def test_delete_appends_history(self, tmp_settings):
        history_path = str(tmp_settings).replace("settings.json", "settings_history.json")
        execute_cell("delete", payload={"setting_key": "log_level"}, service="launcher")
        entries = _load_history(history_path)
        assert any(e["action"] == "DELETE" and e["setting_key"] == "log_level" for e in entries)


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


class TestHistory:
    def test_history_empty_initially(self, tmp_settings):
        body, status = execute_cell("history", service="launcher")
        assert status == 200
        assert body["history"] == []

    def test_history_reflects_actions(self, tmp_settings):
        execute_cell("create", payload={"setting_key": "k", "value": "v"}, service="launcher")
        execute_cell("update", payload={"setting_key": "k", "value": "v2"}, service="launcher")
        body, _ = execute_cell("history", service="launcher")
        assert len(body["history"]) == 2

    def test_history_filters_by_key(self, tmp_settings):
        execute_cell("create", payload={"setting_key": "k1", "value": "v"}, service="launcher")
        execute_cell("create", payload={"setting_key": "k2", "value": "v"}, service="launcher")
        body, _ = execute_cell("history", payload={"setting_key": "k1"}, service="launcher")
        assert all(e["setting_key"] == "k1" for e in body["history"])


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


class TestRollback:
    def test_rollback_success(self, tmp_settings):
        execute_cell("update", payload={"setting_key": "log_level", "value": "DEBUG"}, service="launcher")
        body, status = execute_cell(
            "rollback",
            payload={"setting_key": "log_level", "value": "INFO"},
            service="launcher",
        )
        assert status == 200
        assert body["success"] is True

    def test_rollback_restores_value(self, tmp_settings):
        execute_cell("update", payload={"setting_key": "log_level", "value": "DEBUG"}, service="launcher")
        execute_cell("rollback", payload={"setting_key": "log_level", "value": "INFO"}, service="launcher")
        data = _load_settings(str(tmp_settings))
        assert data["settings"]["log_level"]["value"] == "INFO"

    def test_rollback_missing_key_returns_400(self, tmp_settings):
        body, status = execute_cell("rollback", payload={"value": "x"}, service="launcher")
        assert status == 400

    def test_rollback_missing_value_returns_400(self, tmp_settings):
        body, status = execute_cell(
            "rollback", payload={"setting_key": "log_level"}, service="launcher"
        )
        assert status == 400

    def test_rollback_nonexistent_returns_404(self, tmp_settings):
        body, status = execute_cell(
            "rollback", payload={"setting_key": "ghost", "value": "x"}, service="launcher"
        )
        assert status == 404

    def test_rollback_appends_history(self, tmp_settings):
        history_path = str(tmp_settings).replace("settings.json", "settings_history.json")
        execute_cell("update", payload={"setting_key": "log_level", "value": "DEBUG"}, service="launcher")
        execute_cell("rollback", payload={"setting_key": "log_level", "value": "INFO"}, service="launcher")
        entries = _load_history(history_path)
        assert any(e["action"] == "ROLLBACK" for e in entries)


# ---------------------------------------------------------------------------
# push_redis
# ---------------------------------------------------------------------------


class TestPushRedis:
    def test_push_redis_returns_success(self, tmp_settings):
        body, status = execute_cell("push_redis", service="launcher")
        assert status == 200
        assert body["success"] is True
        assert "pushed" in body

    def test_push_redis_counts_settings(self, tmp_settings):
        body, _ = execute_cell("push_redis", service="launcher")
        assert body["pushed"] == 2


# ---------------------------------------------------------------------------
# coerce_value utility
# ---------------------------------------------------------------------------


class TestCoerceValue:
    def test_coerce_string(self):
        assert _coerce_value("hello", "string") == "hello"

    def test_coerce_number_int(self):
        assert _coerce_value("42", "number") == 42

    def test_coerce_number_float(self):
        assert abs(_coerce_value("3.14", "number") - 3.14) < 0.001

    def test_coerce_boolean_true(self):
        for val in ("true", "True", "1", "yes"):
            assert _coerce_value(val, "boolean") is True

    def test_coerce_boolean_false(self):
        for val in ("false", "False", "0", "no"):
            assert _coerce_value(val, "boolean") is False

    def test_coerce_json_string(self):
        result = _coerce_value('{"a": 1}', "json")
        assert result == {"a": 1}

    def test_coerce_json_dict(self):
        result = _coerce_value({"a": 1}, "json")
        assert result == {"a": 1}

    def test_coerce_invalid_number_raises(self):
        with pytest.raises(ValueError):
            _coerce_value("not-a-num", "number")

    def test_coerce_invalid_boolean_raises(self):
        with pytest.raises(ValueError):
            _coerce_value("maybe", "boolean")

    def test_coerce_invalid_json_raises(self):
        with pytest.raises(ValueError):
            _coerce_value("{not valid json}", "json")


# ---------------------------------------------------------------------------
# Unknown action
# ---------------------------------------------------------------------------


class TestUnknownAction:
    def test_unknown_action_returns_400(self, tmp_settings):
        body, status = execute_cell("explode", service="launcher")
        assert status == 400
        assert "error" in body
