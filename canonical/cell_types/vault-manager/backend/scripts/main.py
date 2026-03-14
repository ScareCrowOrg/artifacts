"""
Vault Manager Cell Backend – CRUD operations on vault.json

Actions:
- list:   Return all secrets (metadata + masked values)
- create: Add new secret to vault
- rotate: Update existing secret value
- delete: Remove secret from vault
- audit:  Query audit trail entries

Phase 3: UI interface for managing secrets.
All write operations append an entry to the in-memory audit log (Redis
integration is stubbed and ready for Phase 2 connection).
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# In-memory audit log – replaced by Redis in production
_audit_log: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def execute_cell(
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    service: str = "launcher",
    **kwargs: Any,
) -> Tuple[Dict[str, Any], int]:
    """Execute a vault manager action and return (response_body, http_status)."""
    if payload is None:
        payload = {}

    vault_path = _resolve_vault_path(service)

    if action == "list":
        return _list_secrets(vault_path)
    if action == "create":
        return _create_secret(vault_path, payload)
    if action == "rotate":
        return _rotate_secret(vault_path, payload)
    if action == "delete":
        return _delete_secret(vault_path, payload)
    if action == "audit":
        return _query_audit(payload)

    return {"error": f"Unknown action: {action}"}, 400


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_vault_path(service: str) -> str:
    tenant = os.getenv("TENANT_NAME", "staging")
    base = os.path.expanduser(f"~/.scareverse/{tenant}/settings")
    return os.path.join(base, "vault.json")


def _load_vault(vault_path: str) -> Dict[str, Any]:
    if not os.path.exists(vault_path):
        return {"secrets": {}}
    with open(vault_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_vault(vault_path: str, vault: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(vault_path), exist_ok=True)
    with open(vault_path, "w", encoding="utf-8") as fh:
        json.dump(vault, fh, indent=2)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit(action: str, secret_key: str, user: str = "system", reason: str = "") -> None:
    _audit_log.append(
        {
            "timestamp": _now(),
            "action": action.upper(),
            "secret_key": secret_key,
            "user": user,
            "reason": reason,
        }
    )


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


def _list_secrets(vault_path: str) -> Tuple[Dict[str, Any], int]:
    """Return all secrets with masked values."""
    vault = _load_vault(vault_path)
    secrets = []
    for key, entry in vault.get("secrets", {}).items():
        raw = entry.get("plaintext", "")
        masked_length = min(len(raw) if raw else 16, 16)
        secrets.append(
            {
                "secret_key": key,
                "category": entry.get("category", "uncategorized"),
                "description": entry.get("description", ""),
                "value": "•" * masked_length,
                "last_updated": entry.get("last_updated"),
            }
        )
    return {"secrets": secrets}, 200


def _create_secret(
    vault_path: str, payload: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """Create a new secret in the vault."""
    secret_key = payload.get("secret_key", "").strip()
    value = payload.get("value", "")

    if not secret_key:
        return {"error": "secret_key is required"}, 400
    if not value:
        return {"error": "value is required"}, 400

    vault = _load_vault(vault_path)
    secrets = vault.setdefault("secrets", {})

    if secret_key in secrets:
        return {"error": f'Secret "{secret_key}" already exists'}, 409

    secrets[secret_key] = {
        "plaintext": value,
        "category": payload.get("category", "api"),
        "description": payload.get("description", ""),
        "last_updated": _now(),
        "created_by": payload.get("user", "system"),
    }

    _save_vault(vault_path, vault)
    _append_audit("CREATE", secret_key, user=payload.get("user", "system"))
    return {"success": True, "secret_key": secret_key}, 201


def _rotate_secret(
    vault_path: str, payload: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """Rotate (update) an existing secret."""
    secret_key = payload.get("secret_key", "").strip()
    new_value = payload.get("new_value", "")

    if not secret_key:
        return {"error": "secret_key is required"}, 400
    if not new_value:
        return {"error": "new_value is required"}, 400

    vault = _load_vault(vault_path)
    secrets = vault.get("secrets", {})

    if secret_key not in secrets:
        return {"error": f'Secret "{secret_key}" not found'}, 404

    secrets[secret_key]["plaintext"] = new_value
    secrets[secret_key]["last_updated"] = _now()
    secrets[secret_key]["rotated_by"] = payload.get("user", "system")

    _save_vault(vault_path, vault)
    _append_audit("ROTATE", secret_key, user=payload.get("user", "system"), reason="manual rotation")
    return {"success": True, "secret_key": secret_key}, 200


def _delete_secret(
    vault_path: str, payload: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """Delete a secret from the vault."""
    secret_key = payload.get("secret_key", "").strip()

    if not secret_key:
        return {"error": "secret_key is required"}, 400

    vault = _load_vault(vault_path)
    secrets = vault.get("secrets", {})

    if secret_key not in secrets:
        return {"error": f'Secret "{secret_key}" not found'}, 404

    del secrets[secret_key]
    _save_vault(vault_path, vault)
    _append_audit("DELETE", secret_key, user=payload.get("user", "system"))
    return {"success": True, "secret_key": secret_key}, 200


def _query_audit(filters: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """Return audit log entries, optionally filtered by secret_key."""
    entries = list(_audit_log)
    key_filter = filters.get("secret_key")
    if key_filter:
        entries = [e for e in entries if e["secret_key"] == key_filter]
    return {"audit": entries}, 200
