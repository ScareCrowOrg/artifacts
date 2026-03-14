"""
Tests for Vault Manager Cell backend scripts.

Covers all CRUD actions: list, create, rotate, delete, audit.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import importlib.util
import pytest

# Load the module directly to avoid hyphen-in-path import issues
_scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_scripts_dir))

from main import execute_cell, _audit_log, _load_vault, _save_vault  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_vault(tmp_path, monkeypatch):
    """Provide a temporary vault.json path and patch TENANT_NAME."""
    tenant_dir = tmp_path / ".scareverse" / "staging" / "settings"
    tenant_dir.mkdir(parents=True)
    vault_path = tenant_dir / "vault.json"
    vault_data = {
        "secrets": {
            "redis-password": {
                "plaintext": "supersecret123",
                "category": "database",
                "description": "Redis main password",
                "last_updated": "2026-01-01T00:00:00+00:00",
                "created_by": "admin",
            }
        }
    }
    vault_path.write_text(json.dumps(vault_data, indent=2))

    # Patch home directory so _resolve_vault_path uses tmp_path
    monkeypatch.setenv("TENANT_NAME", "staging")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Also patch os.path.expanduser via monkeypatching the env
    monkeypatch.setenv("HOME", str(tmp_path))

    return vault_path


@pytest.fixture(autouse=True)
def clear_audit_log():
    """Clear the in-memory audit log before each test."""
    _audit_log.clear()
    yield
    _audit_log.clear()


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestListSecrets:
    def test_list_returns_secrets(self, tmp_vault):
        body, status = execute_cell("list", service="launcher")
        assert status == 200
        assert "secrets" in body
        assert len(body["secrets"]) == 1

    def test_list_masks_value(self, tmp_vault):
        body, status = execute_cell("list", service="launcher")
        assert status == 200
        secret = body["secrets"][0]
        assert "•" in secret["value"]
        assert "supersecret123" not in secret["value"]

    def test_list_includes_metadata(self, tmp_vault):
        body, _ = execute_cell("list", service="launcher")
        secret = body["secrets"][0]
        assert secret["secret_key"] == "redis-password"
        assert secret["category"] == "database"
        assert secret["description"] == "Redis main password"

    def test_list_empty_vault(self, tmp_vault):
        # Overwrite vault with no secrets
        _save_vault(str(tmp_vault), {"secrets": {}})
        body, status = execute_cell("list", service="launcher")
        assert status == 200
        assert body["secrets"] == []


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreateSecret:
    def test_create_success(self, tmp_vault):
        body, status = execute_cell(
            "create",
            payload={"secret_key": "new-key", "value": "new-value", "category": "api"},
            service="launcher",
        )
        assert status == 201
        assert body["success"] is True
        assert body["secret_key"] == "new-key"

    def test_create_persisted_to_vault(self, tmp_vault):
        execute_cell(
            "create",
            payload={"secret_key": "new-key", "value": "new-value"},
            service="launcher",
        )
        vault = _load_vault(str(tmp_vault))
        assert "new-key" in vault["secrets"]

    def test_create_missing_key_returns_400(self, tmp_vault):
        body, status = execute_cell("create", payload={"value": "val"}, service="launcher")
        assert status == 400
        assert "error" in body

    def test_create_missing_value_returns_400(self, tmp_vault):
        body, status = execute_cell("create", payload={"secret_key": "k"}, service="launcher")
        assert status == 400

    def test_create_duplicate_returns_409(self, tmp_vault):
        body, status = execute_cell(
            "create",
            payload={"secret_key": "redis-password", "value": "x"},
            service="launcher",
        )
        assert status == 409

    def test_create_appends_audit_log(self, tmp_vault):
        execute_cell(
            "create",
            payload={"secret_key": "audit-test", "value": "v"},
            service="launcher",
        )
        assert len(_audit_log) == 1
        assert _audit_log[0]["action"] == "CREATE"
        assert _audit_log[0]["secret_key"] == "audit-test"


# ---------------------------------------------------------------------------
# rotate
# ---------------------------------------------------------------------------


class TestRotateSecret:
    def test_rotate_success(self, tmp_vault):
        body, status = execute_cell(
            "rotate",
            payload={"secret_key": "redis-password", "new_value": "rotated-value"},
            service="launcher",
        )
        assert status == 200
        assert body["success"] is True

    def test_rotate_updates_vault(self, tmp_vault):
        execute_cell(
            "rotate",
            payload={"secret_key": "redis-password", "new_value": "rotated-value"},
            service="launcher",
        )
        vault = _load_vault(str(tmp_vault))
        assert vault["secrets"]["redis-password"]["plaintext"] == "rotated-value"

    def test_rotate_missing_key_returns_400(self, tmp_vault):
        body, status = execute_cell(
            "rotate", payload={"new_value": "x"}, service="launcher"
        )
        assert status == 400

    def test_rotate_missing_new_value_returns_400(self, tmp_vault):
        body, status = execute_cell(
            "rotate", payload={"secret_key": "redis-password"}, service="launcher"
        )
        assert status == 400

    def test_rotate_nonexistent_returns_404(self, tmp_vault):
        body, status = execute_cell(
            "rotate",
            payload={"secret_key": "no-such-key", "new_value": "x"},
            service="launcher",
        )
        assert status == 404

    def test_rotate_appends_audit_log(self, tmp_vault):
        execute_cell(
            "rotate",
            payload={"secret_key": "redis-password", "new_value": "v2"},
            service="launcher",
        )
        assert len(_audit_log) == 1
        assert _audit_log[0]["action"] == "ROTATE"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDeleteSecret:
    def test_delete_success(self, tmp_vault):
        body, status = execute_cell(
            "delete",
            payload={"secret_key": "redis-password"},
            service="launcher",
        )
        assert status == 200
        assert body["success"] is True

    def test_delete_removes_from_vault(self, tmp_vault):
        execute_cell("delete", payload={"secret_key": "redis-password"}, service="launcher")
        vault = _load_vault(str(tmp_vault))
        assert "redis-password" not in vault["secrets"]

    def test_delete_missing_key_returns_400(self, tmp_vault):
        body, status = execute_cell("delete", payload={}, service="launcher")
        assert status == 400

    def test_delete_nonexistent_returns_404(self, tmp_vault):
        body, status = execute_cell(
            "delete", payload={"secret_key": "ghost"}, service="launcher"
        )
        assert status == 404

    def test_delete_appends_audit_log(self, tmp_vault):
        execute_cell("delete", payload={"secret_key": "redis-password"}, service="launcher")
        assert len(_audit_log) == 1
        assert _audit_log[0]["action"] == "DELETE"


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


class TestQueryAudit:
    def test_audit_returns_empty_initially(self, tmp_vault):
        body, status = execute_cell("audit", service="launcher")
        assert status == 200
        assert body["audit"] == []

    def test_audit_reflects_actions(self, tmp_vault):
        execute_cell(
            "create",
            payload={"secret_key": "k1", "value": "v1"},
            service="launcher",
        )
        execute_cell(
            "rotate",
            payload={"secret_key": "k1", "new_value": "v2"},
            service="launcher",
        )
        body, status = execute_cell("audit", service="launcher")
        assert status == 200
        assert len(body["audit"]) == 2
        assert body["audit"][0]["action"] == "CREATE"
        assert body["audit"][1]["action"] == "ROTATE"

    def test_audit_filters_by_secret_key(self, tmp_vault):
        execute_cell("create", payload={"secret_key": "k1", "value": "v"}, service="launcher")
        execute_cell("create", payload={"secret_key": "k2", "value": "v"}, service="launcher")
        body, status = execute_cell("audit", payload={"secret_key": "k1"}, service="launcher")
        assert status == 200
        assert all(e["secret_key"] == "k1" for e in body["audit"])


# ---------------------------------------------------------------------------
# Unknown action
# ---------------------------------------------------------------------------


class TestUnknownAction:
    def test_unknown_action_returns_400(self, tmp_vault):
        body, status = execute_cell("explode", service="launcher")
        assert status == 400
        assert "error" in body
