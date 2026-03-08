"""
Unit tests for GateKeeper dynamic config loading.

Validates that:
- _load_job_types_from_artifacts() loads all JSON files correctly.
- _build_job_types_config() builds the expected routing config entries.
- Aliases are expanded so legacy job-type names still resolve.
- Env var overrides replace the JSON-defined endpoint.
- Missing 'name' field in JSON is handled gracefully (file skipped).
- Non-existent job-types directory is handled gracefully (empty dict returned).
- JOB_TYPES_CONFIG is non-empty at module init.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from .. import config
from ..config import _build_job_types_config, _load_job_types_from_artifacts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(directory: Path, filename: str, data: dict) -> Path:
    """Write a JSON file to *directory* and return the file path."""
    path = directory / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _load_job_types_from_artifacts
# ---------------------------------------------------------------------------


class TestLoadJobTypesFromArtifacts:
    def test_loads_all_json_files(self, tmp_path):
        """All valid JSON files in the directory are loaded."""
        _write_json(tmp_path, "worker_a.json", {"name": "worker_a", "endpoint": "http://a:9000"})
        _write_json(tmp_path, "worker_b.json", {"name": "worker_b", "endpoint": "http://b:9000"})

        result = _load_job_types_from_artifacts(tmp_path)
        assert "worker_a" in result
        assert "worker_b" in result

    def test_skips_file_missing_name_field(self, tmp_path):
        """JSON files without a 'name' field are silently skipped."""
        _write_json(tmp_path, "no_name.json", {"endpoint": "http://x:9000"})
        result = _load_job_types_from_artifacts(tmp_path)
        assert result == {}

    def test_missing_directory_returns_empty_dict(self, tmp_path):
        """Non-existent directory returns empty dict without raising."""
        missing_dir = tmp_path / "does_not_exist"
        result = _load_job_types_from_artifacts(missing_dir)
        assert result == {}

    def test_endpoint_from_json(self, tmp_path):
        """Endpoint from JSON file is preserved when env var is absent."""
        _write_json(
            tmp_path,
            "ollama_generate.json",
            {"name": "ollama_generate", "endpoint": "http://scareverse-ollama-worker:9000"},
        )
        result = _load_job_types_from_artifacts(tmp_path)
        assert result["ollama_generate"]["endpoint"] == "http://scareverse-ollama-worker:9000"

    def test_env_var_overrides_json_endpoint(self, tmp_path):
        """WORKER_{NAME}_ENDPOINT env var replaces the JSON endpoint."""
        _write_json(
            tmp_path,
            "ollama_generate.json",
            {"name": "ollama_generate", "endpoint": "http://default-ollama:9000"},
        )
        with patch.dict(os.environ, {"WORKER_OLLAMA_GENERATE_ENDPOINT": "http://custom:9001"}):
            result = _load_job_types_from_artifacts(tmp_path)
        assert result["ollama_generate"]["endpoint"] == "http://custom:9001"

    def test_malformed_json_is_skipped(self, tmp_path):
        """A file with invalid JSON does not raise; other files are still loaded."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json", encoding="utf-8")
        _write_json(tmp_path, "good.json", {"name": "good_worker", "endpoint": "http://g:9000"})

        result = _load_job_types_from_artifacts(tmp_path)
        assert "good_worker" in result
        assert "bad" not in result


# ---------------------------------------------------------------------------
# _build_job_types_config
# ---------------------------------------------------------------------------


class TestBuildJobTypesConfig:
    def test_canonical_name_in_config(self, tmp_path):
        """The canonical name is always present as a key."""
        _write_json(
            tmp_path,
            "rembg_removebackground.json",
            {
                "name": "rembg_removebackground",
                "worker_type": "rembg",
                "endpoint": "http://rembg:9000",
                "queue_l1": "scareverse:cpu-jobs:queue",
                "queue_l2": "scareverse:cpu-jobs:queue",
                "result_storage": "rpush_l1",
                "result_key_prefix": "scareverse:rembg-results",
                "result_key_ttl": 120,
                "timeout": 60,
                "aliases": ["REMOTE_REMBG", "background_removal", "rembg_removebackground"],
            },
        )
        result = _build_job_types_config(tmp_path)
        assert "rembg_removebackground" in result

    def test_aliases_are_expanded(self, tmp_path):
        """Alias keys resolve to the same entry as the canonical name."""
        _write_json(
            tmp_path,
            "rembg_removebackground.json",
            {
                "name": "rembg_removebackground",
                "worker_type": "rembg",
                "endpoint": "http://rembg:9000",
                "queue_l1": "scareverse:cpu-jobs:queue",
                "queue_l2": "scareverse:cpu-jobs:queue",
                "result_storage": "rpush_l1",
                "result_key_prefix": "scareverse:rembg-results",
                "result_key_ttl": 120,
                "timeout": 60,
                "aliases": ["REMOTE_REMBG", "background_removal", "rembg_removebackground"],
            },
        )
        result = _build_job_types_config(tmp_path)
        assert "REMOTE_REMBG" in result
        assert "background_removal" in result
        # All aliases point to the same object
        assert result["REMOTE_REMBG"] is result["rembg_removebackground"]
        assert result["background_removal"] is result["rembg_removebackground"]

    def test_entry_structure(self, tmp_path):
        """Each entry has the required routing keys."""
        _write_json(
            tmp_path,
            "ollama_generate.json",
            {
                "name": "ollama_generate",
                "worker_type": "ollama",
                "endpoint": "http://ollama:9000",
                "queue_l1": "scareverse:cpu-jobs:queue",
                "queue_l2": "scareverse:cpu-jobs:queue",
                "result_storage": "rpush_l1",
                "result_key_prefix": "scareverse:ollama-results",
                "result_key_ttl": 60,
                "timeout": 120,
                "aliases": ["ollama_generate"],
            },
        )
        result = _build_job_types_config(tmp_path)
        entry = result["ollama_generate"]
        assert entry["worker_name"] == "ollama"
        assert entry["endpoint"] == "http://ollama:9000"
        assert entry["queue_l1"] == "scareverse:cpu-jobs:queue"
        assert entry["queue_l2"] == "scareverse:cpu-jobs:queue"
        assert entry["timeout"] == 120
        assert entry["result_storage"] == "rpush_l1"
        assert entry["result_key_prefix"] == "scareverse:ollama-results"
        assert entry["result_key_ttl"] == 60

    def test_empty_directory_returns_empty_dict(self, tmp_path):
        """No JSON files → empty config (graceful degradation)."""
        result = _build_job_types_config(tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# JOB_TYPES_CONFIG: module-level integration
# ---------------------------------------------------------------------------


class TestJobTypesConfigModuleInit:
    def test_config_is_not_empty(self):
        """JOB_TYPES_CONFIG must be populated at module init."""
        assert len(config.JOB_TYPES_CONFIG) > 0

    def test_ollama_generate_present(self):
        """ollama_generate job type is loaded from canonical artifacts."""
        assert "ollama_generate" in config.JOB_TYPES_CONFIG

    def test_ollama_chat_present(self):
        """ollama_chat job type is loaded from canonical artifacts."""
        assert "ollama_chat" in config.JOB_TYPES_CONFIG

    def test_sd_generate_present(self):
        """sd_generate job type is loaded from canonical artifacts."""
        assert "sd_generate" in config.JOB_TYPES_CONFIG

    def test_rembg_removebackground_present(self):
        """rembg_removebackground canonical name is present."""
        assert "rembg_removebackground" in config.JOB_TYPES_CONFIG

    def test_rembg_legacy_aliases_present(self):
        """Legacy rembg aliases (REMOTE_REMBG, background_removal) are still routable."""
        assert "REMOTE_REMBG" in config.JOB_TYPES_CONFIG
        assert "background_removal" in config.JOB_TYPES_CONFIG

    def test_instantmesh_present(self):
        """instantmesh job type is loaded from canonical artifacts."""
        assert "instantmesh" in config.JOB_TYPES_CONFIG

    def test_ollama_generate_endpoint_contains_ollama(self):
        """ollama_generate endpoint points to the ollama worker."""
        endpoint = config.JOB_TYPES_CONFIG["ollama_generate"]["endpoint"]
        assert endpoint is not None
        assert "ollama" in endpoint.lower()

    def test_rembg_endpoint_contains_rembg(self):
        """REMOTE_REMBG endpoint points to the rembg worker."""
        endpoint = config.JOB_TYPES_CONFIG["REMOTE_REMBG"]["endpoint"]
        assert endpoint is not None
        assert "rembg" in endpoint.lower()

    def test_sd_generate_endpoint_contains_sd(self):
        """sd_generate endpoint points to the stable-diffusion worker."""
        endpoint = config.JOB_TYPES_CONFIG["sd_generate"]["endpoint"]
        assert endpoint is not None
        assert "sd" in endpoint.lower()

    def test_instantmesh_queue_is_3d(self):
        """instantmesh routes to the 3D jobs queue."""
        entry = config.JOB_TYPES_CONFIG["instantmesh"]
        assert "3d-jobs" in entry["queue_l1"]

    def test_env_var_override_at_module_level(self):
        """Reloading config with env var override changes the endpoint."""
        with patch.dict(os.environ, {"WORKER_OLLAMA_GENERATE_ENDPOINT": "http://test-ollama:1234"}):
            rebuilt = _build_job_types_config()
        assert rebuilt["ollama_generate"]["endpoint"] == "http://test-ollama:1234"

    def test_all_queues_l1_derived_from_config(self):
        """ALL_QUEUES_L1 is non-empty and contains expected queue names."""
        assert len(config.ALL_QUEUES_L1) > 0
        assert "scareverse:cpu-jobs:queue" in config.ALL_QUEUES_L1

    def test_all_queues_l2_derived_from_config(self):
        """ALL_QUEUES_L2 is non-empty and contains expected queue names."""
        assert len(config.ALL_QUEUES_L2) > 0
        assert "scareverse:cpu-jobs:queue" in config.ALL_QUEUES_L2

