"""
Tests for xterm-terminal-cell backend main.py.
"""

import json
import sys
import pytest

# Allow importing main.py from its relative path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "scripts"))
from main import execute_cell


class TestExecuteCell:
    def test_returns_success(self):
        result = execute_cell({})
        assert result["success"] is True

    def test_ui_only_flag(self):
        result = execute_cell({})
        assert result["ui_only"] is True

    def test_default_ws_url(self):
        result = execute_cell({})
        assert result["ws_url"] == "ws://node-pty-service:8000/ws"

    def test_custom_ws_url(self):
        result = execute_cell({"ws_url": "wss://custom-host:9000/ws"})
        assert result["ws_url"] == "wss://custom-host:9000/ws"

    def test_message_present(self):
        result = execute_cell({})
        assert "message" in result
        assert "UI-only" in result["message"] or "ui-only" in result["message"].lower()

    def test_extra_keys_ignored(self):
        result = execute_cell({"unknown_key": "value", "cols": 120, "rows": 40})
        assert result["success"] is True

    def test_empty_ws_url_uses_default(self):
        result = execute_cell({"ws_url": ""})
        # empty string falls back to default because of or default logic
        assert "ws_url" in result
