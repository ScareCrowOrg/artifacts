"""
Unit tests for GateKeeper dynamic config loading.

Validates that:
- _load_job_types_from_artifacts() loads all JSON files correctly.
- _build_job_types_config() builds the expected routing config entries.
- execution_model is correctly parsed for both service and subprocess types.
- Aliases are expanded so legacy job-type names still resolve.
- Env var overrides replace the JSON-defined endpoint for service workers.
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
    path = directory / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _load_job_types_from_artifacts
# ---------------------------------------------------------------------------


class TestLoadJobTypesFromArtifacts:
    def test_loads_all_json_files(self, tmp_path):
        _write_json(tmp_path, "worker_a.json", {"name": "worker_a", "endpoint": "http://a:9000"})
        _write_json(tmp_path, "worker_b.json", {"name": "worker_b", "endpoint": "http://b:9000"})

        result = _load_job_types_from_artifacts(tmp_path)
        assert "worker_a" in result
        assert "worker_b" in result

    def test_skips_file_missing_name_field(self, tmp_path):
        _write_json(tmp_path, "no_name.json", {"endpoint": "http://x:9000"})
        result = _load_job_types_from_artifacts(tmp_path)
        assert result == {}

    def test_missing_directory_returns_empty_dict(self, tmp_path):
        missing_dir = tmp_path / "does_not_exist"
        result = _load_job_types_from_artifacts(missing_dir)
        assert result == {}

    def test_endpoint_from_json(self, tmp_path):
        _write_json(
            tmp_path,
            "ollama_generate.json",
            {
                "name": "ollama_generate",
                "execution_model": "service",
                "service": {"name": "ollama", "endpoint": "http://scareverse-ollama-service:9000"},
            },
        )
        result = _load_job_types_from_artifacts(tmp_path)
        assert result["ollama_generate"]["service"]["endpoint"] == "http://scareverse-ollama-service:9000"

    def test_env_var_overrides_service_endpoint(self, tmp_path):
        """WORKER_{NAME}_ENDPOINT env var replaces the service endpoint."""
        _write_json(
            tmp_path,
            "ollama_generate.json",
            {
                "name": "ollama_generate",
                "execution_model": "service",
                "service": {"name": "ollama", "endpoint": "http://default-ollama:9000"},
            },
        )
        with patch.dict(os.environ, {"WORKER_OLLAMA_GENERATE_ENDPOINT": "http://custom:9001"}):
            result = _load_job_types_from_artifacts(tmp_path)
        assert result["ollama_generate"]["service"]["endpoint"] == "http://custom:9001"

    def test_malformed_json_is_skipped(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json", encoding="utf-8")
        _write_json(tmp_path, "good.json", {"name": "good_worker", "endpoint": "http://g:9000"})

        result = _load_job_types_from_artifacts(tmp_path)
        assert "good_worker" in result
        assert "bad" not in result

    def test_subprocess_worker_has_worker_path(self, tmp_path):
        """Subprocess worker definitions include worker.path."""
        _write_json(
            tmp_path,
            "rembg.json",
            {
                "name": "rembg_removebackground",
                "execution_model": "subprocess",
                "worker": {
                    "path": "artifacts/canonical/workers/rembg",
                    "entry_point": "main.py",
                },
            },
        )
        result = _load_job_types_from_artifacts(tmp_path)
        assert result["rembg_removebackground"]["worker"]["path"] == "artifacts/canonical/workers/rembg"


# ---------------------------------------------------------------------------
# _build_job_types_config
# ---------------------------------------------------------------------------


class TestBuildJobTypesConfig:
    def test_canonical_name_in_config(self, tmp_path):
        _write_json(
            tmp_path,
            "rembg_removebackground.json",
            {
                "name": "rembg_removebackground",
                "execution_model": "subprocess",
                "worker": {"path": "artifacts/canonical/workers/rembg", "entry_point": "main.py"},
                "configuration": {"timeout_seconds": 60},
                "queue_l1": "scareverse:cpu-jobs:queue",
                "queue_l2": "scareverse:cpu-jobs:queue",
                "result_storage": "rpush_l1",
                "result_key_prefix": "scareverse:rembg-results",
                "result_key_ttl": 120,
                "aliases": ["REMOTE_REMBG", "background_removal", "rembg_removebackground"],
            },
        )
        result = _build_job_types_config(tmp_path)
        assert "rembg_removebackground" in result

    def test_aliases_are_expanded(self, tmp_path):
        _write_json(
            tmp_path,
            "rembg_removebackground.json",
            {
                "name": "rembg_removebackground",
                "execution_model": "subprocess",
                "worker": {"path": "artifacts/canonical/workers/rembg", "entry_point": "main.py"},
                "configuration": {"timeout_seconds": 60},
                "queue_l1": "scareverse:cpu-jobs:queue",
                "queue_l2": "scareverse:cpu-jobs:queue",
                "result_storage": "rpush_l1",
                "result_key_prefix": "scareverse:rembg-results",
                "result_key_ttl": 120,
                "aliases": ["REMOTE_REMBG", "background_removal", "rembg_removebackground"],
            },
        )
        result = _build_job_types_config(tmp_path)
        assert "REMOTE_REMBG" in result
        assert "background_removal" in result
        assert result["REMOTE_REMBG"] is result["rembg_removebackground"]
        assert result["background_removal"] is result["rembg_removebackground"]

    def test_service_entry_structure(self, tmp_path):
        """Service entries have endpoint, queue_l1, timeout, result_storage."""
        _write_json(
            tmp_path,
            "ollama_generate.json",
            {
                "name": "ollama_generate",
                "execution_model": "service",
                "service": {"name": "ollama", "endpoint": "http://ollama:9000"},
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
        assert entry["execution_model"] == "service"
        assert entry["endpoint"] == "http://ollama:9000"
        assert entry["queue_l1"] == "scareverse:cpu-jobs:queue"
        assert entry["queue_l2"] == "scareverse:cpu-jobs:queue"
        assert entry["timeout"] == 120
        assert entry["result_storage"] == "rpush_l1"
        assert entry["result_key_prefix"] == "scareverse:ollama-results"
        assert entry["result_key_ttl"] == 60

    def test_subprocess_entry_structure(self, tmp_path):
        """Subprocess entries have execution_model, worker config, no endpoint."""
        _write_json(
            tmp_path,
            "rembg.json",
            {
                "name": "rembg_removebackground",
                "execution_model": "subprocess",
                "worker": {"path": "artifacts/canonical/workers/rembg", "entry_point": "main.py"},
                "configuration": {"timeout_seconds": 60},
                "queue_l1": "scareverse:cpu-jobs:queue",
                "queue_l2": "scareverse:cpu-jobs:queue",
                "result_storage": "rpush_l1",
                "result_key_prefix": "scareverse:rembg-results",
                "result_key_ttl": 120,
                "aliases": ["rembg_removebackground"],
            },
        )
        result = _build_job_types_config(tmp_path)
        entry = result["rembg_removebackground"]
        assert entry["execution_model"] == "subprocess"
        assert entry["worker"]["path"] == "artifacts/canonical/workers/rembg"
        assert "endpoint" not in entry

    def test_empty_directory_returns_empty_dict(self, tmp_path):
        result = _build_job_types_config(tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# JOB_TYPES_CONFIG: module-level integration
# ---------------------------------------------------------------------------


class TestJobTypesConfigModuleInit:
    def test_config_is_not_empty(self):
        assert len(config.JOB_TYPES_CONFIG) > 0

    def test_ollama_generate_present(self):
        assert "ollama_generate" in config.JOB_TYPES_CONFIG

    def test_ollama_chat_present(self):
        assert "ollama_chat" in config.JOB_TYPES_CONFIG

    def test_sd_generate_present(self):
        assert "sd_generate" in config.JOB_TYPES_CONFIG

    def test_rembg_removebackground_present(self):
        assert "rembg_removebackground" in config.JOB_TYPES_CONFIG

    def test_rembg_legacy_aliases_present(self):
        assert "REMOTE_REMBG" in config.JOB_TYPES_CONFIG
        assert "background_removal" in config.JOB_TYPES_CONFIG

    def test_instantmesh_present(self):
        assert "instantmesh" in config.JOB_TYPES_CONFIG

    def test_ollama_generate_is_service_worker(self):
        """ollama_generate uses service execution model."""
        entry = config.JOB_TYPES_CONFIG["ollama_generate"]
        assert entry.get("execution_model") == "service"
        assert entry.get("endpoint") is not None
        assert "ollama" in entry["endpoint"].lower()

    def test_sd_generate_is_service_worker(self):
        """sd_generate uses service execution model."""
        entry = config.JOB_TYPES_CONFIG["sd_generate"]
        assert entry.get("execution_model") == "service"
        assert entry.get("endpoint") is not None

    def test_rembg_is_subprocess_worker(self):
        """rembg_removebackground uses subprocess execution model."""
        entry = config.JOB_TYPES_CONFIG["rembg_removebackground"]
        assert entry.get("execution_model") == "subprocess"
        assert "worker" in entry
        assert "path" in entry["worker"]

    def test_rembg_worker_path_contains_rembg(self):
        """Rembg worker path points to the workers/rembg directory."""
        entry = config.JOB_TYPES_CONFIG["rembg_removebackground"]
        assert "rembg" in entry["worker"]["path"].lower()

    def test_instantmesh_queue_is_3d(self):
        entry = config.JOB_TYPES_CONFIG["instantmesh"]
        assert "3d-jobs" in entry["queue_l1"]

    def test_env_var_override_at_module_level(self):
        """Reloading config with env var override changes the endpoint."""
        with patch.dict(os.environ, {"WORKER_OLLAMA_GENERATE_ENDPOINT": "http://test-ollama:1234"}):
            rebuilt = _build_job_types_config()
        assert rebuilt["ollama_generate"]["endpoint"] == "http://test-ollama:1234"

    def test_all_queues_l1_derived_from_config(self):
        assert len(config.ALL_QUEUES_L1) > 0
        assert "scareverse:cpu-jobs:queue" in config.ALL_QUEUES_L1

    def test_all_queues_l2_derived_from_config(self):
        assert len(config.ALL_QUEUES_L2) > 0
        assert "scareverse:cpu-jobs:queue" in config.ALL_QUEUES_L2
