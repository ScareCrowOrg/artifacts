"""
Settings Manager Cell Backend – CRUD operations on settings.json

Actions:
- list:        Return all settings grouped by category
- create:      Add new setting with type validation
- update:      Update existing setting value
- delete:      Remove setting
- history:     Return modification history
- rollback:    Restore previous value
- push_redis:  Push all settings to Redis L1 (stub, ready for Phase 2)

Phase 3: UI interface for managing settings.
Modification history is maintained in settings_history.json alongside the
main settings file.  Redis push is stubbed and ready for Phase 1B wiring.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union


_VALID_TYPES = ("string", "number", "boolean", "json")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def execute_cell(
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    service: str = "launcher",
    **kwargs: Any,
) -> Tuple[Dict[str, Any], int]:
    """Execute a settings manager action and return (response_body, http_status)."""
    if payload is None:
        payload = {}

    settings_path, history_path = _resolve_paths(service)

    if action == "list":
        return _list_settings(settings_path)
    if action == "create":
        return _create_setting(settings_path, history_path, payload)
    if action == "update":
        return _update_setting(settings_path, history_path, payload)
    if action == "delete":
        return _delete_setting(settings_path, history_path, payload)
    if action == "history":
        return _get_history(history_path, payload)
    if action == "rollback":
        return _rollback_setting(settings_path, history_path, payload)
    if action == "push_redis":
        return _push_to_redis(settings_path)

    return {"error": f"Unknown action: {action}"}, 400


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _resolve_paths(service: str) -> Tuple[str, str]:
    tenant = os.getenv("TENANT_NAME", "staging")
    base = os.path.expanduser(f"~/.scareverse/{tenant}/settings")
    return os.path.join(base, "settings.json"), os.path.join(base, "settings_history.json")


def _load_settings(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"settings": {}}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_settings(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def _load_history(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_history(path: str, entries: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_history(
    history_path: str,
    action: str,
    setting_key: str,
    previous_value: Any = None,
    new_value: Any = None,
    user: str = "system",
) -> None:
    entries = _load_history(history_path)
    entries.append(
        {
            "timestamp": _now(),
            "action": action.upper(),
            "setting_key": setting_key,
            "previous_value": previous_value,
            "new_value": new_value,
            "user": user,
        }
    )
    _save_history(history_path, entries)


def _coerce_value(raw: Union[str, int, float, bool, None], setting_type: str) -> Any:
    """Coerce raw string input to the declared setting type."""
    if setting_type == "number":
        try:
            return float(raw) if "." in str(raw) else int(raw)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            raise ValueError(f"Cannot coerce '{raw}' to number")
    if setting_type == "boolean":
        if isinstance(raw, bool):
            return raw
        if str(raw).lower() in ("true", "1", "yes"):
            return True
        if str(raw).lower() in ("false", "0", "no"):
            return False
        raise ValueError(f"Cannot coerce '{raw}' to boolean")
    if setting_type == "json":
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)  # type: ignore[arg-type]
        except (json.JSONDecodeError, TypeError):
            raise ValueError(f"Invalid JSON: {raw}")
    # string fallback
    return str(raw) if raw is not None else ""


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


def _list_settings(settings_path: str) -> Tuple[Dict[str, Any], int]:
    """Return all settings with metadata."""
    data = _load_settings(settings_path)
    settings_list = []
    for key, entry in data.get("settings", {}).items():
        settings_list.append(
            {
                "setting_key": key,
                "category": entry.get("category", "general"),
                "type": entry.get("type", "string"),
                "value": entry.get("value"),
                "last_updated": entry.get("last_updated"),
            }
        )
    return {"settings": settings_list}, 200


def _create_setting(
    settings_path: str, history_path: str, payload: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """Create a new setting."""
    setting_key = payload.get("setting_key", "").strip()
    if not setting_key:
        return {"error": "setting_key is required"}, 400

    raw_value = payload.get("value")
    if raw_value is None or raw_value == "":
        return {"error": "value is required"}, 400

    setting_type = payload.get("type", "string")
    if setting_type not in _VALID_TYPES:
        return {"error": f"Invalid type. Must be one of: {_VALID_TYPES}"}, 400

    try:
        coerced = _coerce_value(raw_value, setting_type)
    except ValueError as exc:
        return {"error": str(exc)}, 422

    data = _load_settings(settings_path)
    settings = data.setdefault("settings", {})

    if setting_key in settings:
        return {"error": f'Setting "{setting_key}" already exists'}, 409

    settings[setting_key] = {
        "value": coerced,
        "type": setting_type,
        "category": payload.get("category", "general"),
        "last_updated": _now(),
        "created_by": payload.get("user", "system"),
    }

    _save_settings(settings_path, data)
    _append_history(
        history_path, "CREATE", setting_key,
        previous_value=None, new_value=coerced,
        user=payload.get("user", "system"),
    )
    return {"success": True, "setting_key": setting_key}, 201


def _update_setting(
    settings_path: str, history_path: str, payload: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """Update an existing setting value."""
    setting_key = payload.get("setting_key", "").strip()
    if not setting_key:
        return {"error": "setting_key is required"}, 400

    new_raw = payload.get("value")
    if new_raw is None or new_raw == "":
        return {"error": "value is required"}, 400

    data = _load_settings(settings_path)
    settings = data.get("settings", {})

    if setting_key not in settings:
        return {"error": f'Setting "{setting_key}" not found'}, 404

    setting_type = settings[setting_key].get("type", "string")
    try:
        coerced = _coerce_value(new_raw, setting_type)
    except ValueError as exc:
        return {"error": str(exc)}, 422

    previous = settings[setting_key].get("value")
    settings[setting_key]["value"] = coerced
    settings[setting_key]["last_updated"] = _now()
    settings[setting_key]["updated_by"] = payload.get("user", "system")

    _save_settings(settings_path, data)
    _append_history(
        history_path, "UPDATE", setting_key,
        previous_value=previous, new_value=coerced,
        user=payload.get("user", "system"),
    )
    return {"success": True, "setting_key": setting_key}, 200


def _delete_setting(
    settings_path: str, history_path: str, payload: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """Delete a setting."""
    setting_key = payload.get("setting_key", "").strip()
    if not setting_key:
        return {"error": "setting_key is required"}, 400

    data = _load_settings(settings_path)
    settings = data.get("settings", {})

    if setting_key not in settings:
        return {"error": f'Setting "{setting_key}" not found'}, 404

    previous = settings[setting_key].get("value")
    del settings[setting_key]
    _save_settings(settings_path, data)
    _append_history(
        history_path, "DELETE", setting_key,
        previous_value=previous, new_value=None,
        user=payload.get("user", "system"),
    )
    return {"success": True, "setting_key": setting_key}, 200


def _get_history(
    history_path: str, filters: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """Return modification history, optionally filtered."""
    entries = _load_history(history_path)
    key_filter = filters.get("setting_key")
    if key_filter:
        entries = [e for e in entries if e["setting_key"] == key_filter]
    return {"history": entries}, 200


def _rollback_setting(
    settings_path: str, history_path: str, payload: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """Restore a setting to a previous value."""
    setting_key = payload.get("setting_key", "").strip()
    restore_value = payload.get("value")

    if not setting_key:
        return {"error": "setting_key is required"}, 400
    if restore_value is None:
        return {"error": "value to restore is required"}, 400

    data = _load_settings(settings_path)
    settings = data.get("settings", {})

    if setting_key not in settings:
        return {"error": f'Setting "{setting_key}" not found'}, 404

    previous = settings[setting_key].get("value")
    settings[setting_key]["value"] = restore_value
    settings[setting_key]["last_updated"] = _now()
    settings[setting_key]["updated_by"] = payload.get("user", "system")

    _save_settings(settings_path, data)
    _append_history(
        history_path, "ROLLBACK", setting_key,
        previous_value=previous, new_value=restore_value,
        user=payload.get("user", "system"),
    )
    return {"success": True, "setting_key": setting_key}, 200


def _push_to_redis(settings_path: str) -> Tuple[Dict[str, Any], int]:
    """Push all settings to Redis L1 (stub – Phase 1B wiring)."""
    data = _load_settings(settings_path)
    count = len(data.get("settings", {}))
    # TODO: Phase 1B – iterate settings and push each key to Redis
    return {"success": True, "pushed": count, "note": "Redis push stubbed (Phase 1B)"}, 200
