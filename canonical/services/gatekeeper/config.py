"""
Configuration module for GateKeeper Service.

Phase 4A Update: Adopted centralized config_manager for lazy loading.
- All settings resolved via get_config() (Redis L1 → env fallback)
- Secrets resolved via vault.* prefix (SecretClient → env fallback)
- Module-level __getattr__ provides backward-compatible lazy resolution
- Config classes group related settings with type-safe static methods

Original description:
Manages dual-source Redis configuration (L1 owner + L2 global),
multi-source pooling strategy, and routing to workers (HTTP services
or subprocess job workers).

Job types are loaded dynamically from artifacts/canonical/job-types/*.json.
Each job type includes an ``execution_model`` field:
  - "service": route via HTTP POST to a long-lived service endpoint.
  - "subprocess": spawn an isolated Python subprocess from artifacts/workers/.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Configure logging EARLY (before importing config_manager) so all loggers work
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Lazy configuration resolution via config_manager
# Falls back gracefully when Redis / SecretClient are unavailable
try:
    from artifacts.shared.config_manager import get_config as _get_config
    logger.info("[Config] ✅ config_manager imported successfully")
except ImportError as e:
    logger.warning(f"[Config] ⚠️ config_manager import failed: {e} - trying relative path...")
    # Fallback: add relative path to shared + setup sys.modules for relative imports
    # From /app/gatekeeper/ → ../artifacts/shared/
    try:
        shared_path = os.path.join(os.path.dirname(__file__), '..', 'artifacts', 'shared')
        crypto_path = os.path.join(shared_path, 'crypto')

        # Resolve to absolute paths and verify they exist
        shared_path = os.path.abspath(shared_path)
        crypto_path = os.path.abspath(crypto_path)

        logger.info(f"[Config] Resolved paths: shared={shared_path}, crypto={crypto_path}")
        logger.info(f"[Config] shared exists: {os.path.exists(shared_path)}, crypto exists: {os.path.exists(crypto_path)}")

        sys.path.insert(0, shared_path)
        sys.path.insert(0, crypto_path)

        logger.debug(f"[Config] Added to sys.path: {shared_path}")
        logger.debug(f"[Config] Added to sys.path: {crypto_path}")

        # Setup sys.modules so relative imports work
        import types
        import importlib.util

        # Create shared package
        shared_module = types.ModuleType('shared')
        shared_module.__path__ = [shared_path]
        sys.modules['shared'] = shared_module

        # CRITICAL: Execute crypto module FIRST (because secret_client depends on it)
        # Crypto is a package (directory), so point to its __init__.py
        crypto_init_path = os.path.join(crypto_path, "__init__.py")
        spec_crypto = importlib.util.spec_from_file_location(
            "shared.crypto",
            crypto_init_path,
            submodule_search_locations=[crypto_path]
        )
        if spec_crypto is None:
            logger.error(f"[Config] ❌ Cannot load crypto from {crypto_init_path}")
            raise ImportError(f"Cannot load shared.crypto from {crypto_init_path}")
        crypto_module = importlib.util.module_from_spec(spec_crypto)
        crypto_module.__path__ = [crypto_path]
        sys.modules['shared.crypto'] = crypto_module
        spec_crypto.loader.exec_module(crypto_module)
        logger.debug(f"[Config] Executed shared.crypto module")

        # THEN execute secret_client (which imports from crypto)
        secret_client_path = os.path.join(shared_path, "secret_client.py")
        spec = importlib.util.spec_from_file_location("shared.secret_client", secret_client_path)
        if spec is None:
            logger.error(f"[Config] ❌ Cannot load secret_client from {secret_client_path}")
            raise ImportError(f"Cannot load shared.secret_client from {secret_client_path}")
        secret_client_module = importlib.util.module_from_spec(spec)
        sys.modules['shared.secret_client'] = secret_client_module
        spec.loader.exec_module(secret_client_module)
        logger.debug(f"[Config] Executed shared.secret_client module")

        # Now import config_manager which has relative imports
        # CRITICAL: Import as 'shared.config_manager' so relative imports work inside it
        logger.debug("[Config] About to import config_manager as shared.config_manager...")
        config_manager_path = os.path.join(shared_path, "config_manager.py")
        spec_cm = importlib.util.spec_from_file_location("shared.config_manager", config_manager_path)
        if spec_cm is None:
            logger.error(f"[Config] ❌ Cannot load config_manager from {config_manager_path}")
            raise ImportError(f"Cannot load shared.config_manager from {config_manager_path}")
        config_manager_module = importlib.util.module_from_spec(spec_cm)
        sys.modules['shared.config_manager'] = config_manager_module
        spec_cm.loader.exec_module(config_manager_module)
        _get_config = config_manager_module.get_config
        logger.info("[Config] ✅ config_manager imported successfully (via relative path + sys.modules setup)")
        logger.info("[Config] ✅ sys.modules ready: shared, shared.crypto, shared.secret_client, shared.config_manager")
    except ImportError as e2:
        logger.error(f"[Config] ❌ config_manager import failed even with relative path: {e2} - using env fallback only")
        # Fallback: resolve directly from environment when artifacts not on path
        def _get_config(key: str) -> Optional[str]:  # type: ignore[misc]
            env_key = key.replace("vault.", "").upper().replace(":", "_").replace(".", "_").replace("-", "_")
            return os.getenv(env_key)

# ============================================================================
# Base Paths
# ============================================================================

BASE_DIR = Path(__file__).parent.absolute()

# ============================================================================
# Config Classes – Lazy-Loading Static Methods
# ============================================================================


class RedisL1Config:
    """Lazy-loading Redis L1 configuration."""

    @staticmethod
    def host() -> str:
        return _get_config("redis_l1_host") or "redis-local"

    @staticmethod
    def port() -> int:
        try:
            value = _get_config("redis_l1_port")
            return int(value) if value else 6380
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid REDIS_L1_PORT value, using default 6380")
            return 6380

    @staticmethod
    def password() -> str:
        """Resolve from vault.redis_password (secret)."""
        return _get_config("vault.redis_password") or "scarerunner"

    @staticmethod
    def db() -> int:
        try:
            value = _get_config("redis_l1_db")
            return int(value) if value else 0
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid REDIS_L1_DB value, using default 0")
            return 0


class CentralHubConfig:
    """Lazy-loading CentralHub configuration."""

    @staticmethod
    def url() -> str:
        return _get_config("centralhub_url") or "http://centralhub:8080"

    @staticmethod
    def service_token() -> str:
        """Resolve from vault.centralhub_pat (secret)."""
        logger.info("[CentralHubConfig] ▶️ Requesting vault.centralhub_pat...")
        token = _get_config("vault.centralhub_pat")
        if token:
            preview = token[:15] if len(token) >= 15 else token
            logger.info(f"[CentralHubConfig] ✅ vault.centralhub_pat resolved (first 15 chars): {preview}...")
            return token
        else:
            logger.warning("[CentralHubConfig] ⚠️ vault.centralhub_pat returned None, using fallback: internal-gatekeeper-token")
            return "internal-gatekeeper-token"


class QueueConfig:
    """Lazy-loading queue configuration."""

    @staticmethod
    def priority() -> str:
        return _get_config("queue_priority") or "owner_first"

    @staticmethod
    def brpop_l1_timeout() -> int:
        try:
            value = _get_config("brpop_l1_timeout")
            return int(value) if value else 1
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid BRPOP_L1_TIMEOUT value, using default 1")
            return 1

    @staticmethod
    def brpop_l2_timeout() -> int:
        try:
            value = _get_config("brpop_l2_timeout")
            return int(value) if value else 20
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid BRPOP_L2_TIMEOUT value, using default 20")
            return 20

    @staticmethod
    def cpu_jobs_queue_l1() -> str:
        return _get_config("cpu_jobs_queue_l1") or "scareverse:cpu-jobs:queue"

    @staticmethod
    def cpu_jobs_queue_l2() -> str:
        return _get_config("cpu_jobs_queue_l2") or "scareverse:cpu-jobs:queue"

    @staticmethod
    def three_d_jobs_queue_l1() -> str:
        return _get_config("three_d_jobs_queue_l1") or "scareverse:3d-jobs:queue"

    @staticmethod
    def three_d_jobs_queue_l2() -> str:
        return _get_config("three_d_jobs_queue_l2") or "scareverse:3d-jobs:queue"

    @staticmethod
    def dead_letter_queue() -> str:
        return _get_config("dead_letter_queue") or "scareverse:dead-letter:queue"

    @staticmethod
    def commands_queue() -> str:
        return _get_config("commands_queue") or "commands:gatekeeper:queue"


class WorkerConfig:
    """Lazy-loading worker configuration."""

    @staticmethod
    def worker_id() -> str:
        return _get_config("worker_id") or "gatekeeper-01"

    @staticmethod
    def heartbeat_interval() -> int:
        try:
            # Try WORKER_HEARTBEAT_INTERVAL first (for backward compatibility)
            # Fall back to HEARTBEAT_INTERVAL (Launcher-injected global default)
            value = _get_config("worker_heartbeat_interval") or _get_config("heartbeat_interval")
            return int(value) if value else 30
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid heartbeat interval value, using default 30")
            return 30

    @staticmethod
    def max_retries() -> int:
        try:
            value = _get_config("worker_max_retries")
            return int(value) if value else 3
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid WORKER_MAX_RETRIES value, using default 3")
            return 3

    @staticmethod
    def retry_delay() -> float:
        try:
            value = _get_config("worker_retry_delay")
            return float(value) if value else 2.0
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid WORKER_RETRY_DELAY value, using default 2.0")
            return 2.0


class TelemetryConfig:
    """Lazy-loading telemetry and orchestration configuration."""

    @staticmethod
    def telemetry_key() -> str:
        return _get_config("telemetry_key") or "state:host:telemetry"

    @staticmethod
    def stale_after_seconds() -> int:
        try:
            value = _get_config("telemetry_stale_after_seconds")
            return int(value) if value else 15
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid TELEMETRY_STALE_AFTER_SECONDS value, using default 15")
            return 15

    @staticmethod
    def scale_up_vram_min_mb() -> int:
        try:
            value = _get_config("scale_up_vram_min_mb")
            return int(value) if value else 3000
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid SCALE_UP_VRAM_MIN_MB value, using default 3000")
            return 3000

    @staticmethod
    def scale_up_ram_min_mb() -> int:
        try:
            value = _get_config("scale_up_ram_min_mb")
            return int(value) if value else 2000
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid SCALE_UP_RAM_MIN_MB value, using default 2000")
            return 2000

    @staticmethod
    def scale_up_queue_depth() -> int:
        try:
            value = _get_config("scale_up_queue_depth")
            return int(value) if value else 5
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid SCALE_UP_QUEUE_DEPTH value, using default 5")
            return 5

    @staticmethod
    def scale_down_idle_seconds() -> int:
        try:
            value = _get_config("scale_down_idle_seconds")
            return int(value) if value else 300
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid SCALE_DOWN_IDLE_SECONDS value, using default 300")
            return 300

    @staticmethod
    def worker_state_key_prefix() -> str:
        return _get_config("worker_state_key_prefix") or "workers:state"


class HttpConfig:
    """Lazy-loading HTTP client configuration."""

    @staticmethod
    def request_timeout() -> int:
        try:
            value = _get_config("http_request_timeout")
            return int(value) if value else 60
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid HTTP_REQUEST_TIMEOUT value, using default 60")
            return 60

    @staticmethod
    def connect_timeout() -> int:
        try:
            value = _get_config("http_connect_timeout")
            return int(value) if value else 10
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid HTTP_CONNECT_TIMEOUT value, using default 10")
            return 10


class HealthCheckConfig:
    """Lazy-loading health check configuration."""

    @staticmethod
    def venv_health_check_interval() -> int:
        try:
            value = _get_config("venv_health_check_interval")
            return int(value) if value else 60
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid VENV_HEALTH_CHECK_INTERVAL value, using default 60")
            return 60

    @staticmethod
    def service_health_probe_timeout() -> float:
        try:
            value = _get_config("service_health_probe_timeout")
            return float(value) if value else 5.0
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid SERVICE_HEALTH_PROBE_TIMEOUT value, using default 5.0")
            return 5.0


class LoggingConfig:
    """Lazy-loading logging configuration."""

    @staticmethod
    def log_level() -> str:
        return _get_config("log_level") or "INFO"

    @staticmethod
    def log_format() -> str:
        return (
            _get_config("log_format")
            or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    @staticmethod
    def log_format_type() -> str:
        return _get_config("log_format_type") or "text"


class JobStateConfig:
    """Lazy-loading job state configuration."""

    @staticmethod
    def key_prefix() -> str:
        return _get_config("job_state_key_prefix") or "state:job"

    @staticmethod
    def ttl_seconds() -> int:
        try:
            value = _get_config("job_state_ttl_seconds")
            return int(value) if value else 3600
        except (ValueError, TypeError):
            logger.warning("[Config] Invalid JOB_STATE_TTL_SECONDS value, using default 3600")
            return 3600


# ============================================================================
# Subprocess Workers Path (computed at import-time, not lazy)
# ============================================================================

_default_workers_path = Path("/app/artifacts/canonical/workers")
if not _default_workers_path.exists():
    try:
        # services/gatekeeper/config.py → 3 parents up = canonical/
        _default_workers_path = Path(__file__).resolve().parents[2] / "workers"
    except IndexError:
        _default_workers_path = Path(__file__).parent / "workers"

WORKERS_PATH = Path(os.getenv("WORKERS_PATH", str(_default_workers_path)))

# ============================================================================
# Job Routing: Dynamic Job Type → Configuration
# ============================================================================

def _load_job_types_from_artifacts(
    job_types_dir: "Path | None" = None,
) -> Dict[str, Any]:
    """
    Load job-type definitions from artifacts/canonical/job-types/*.json.

    Endpoint can be overridden via env var ``WORKER_{NAME_UPPER}_ENDPOINT``.
    """
    if job_types_dir is None:
        # Docker path: /app/artifacts/canonical/job-types
        candidate = Path("/app/artifacts/canonical/job-types")
        if not candidate.exists():
            try:
                # services/gatekeeper/config.py → 3 parents = canonical/ → job-types/
                candidate = Path(__file__).resolve().parents[2] / "job-types"
            except IndexError:
                candidate = Path(__file__).parent / "job-types"
        job_types_dir = candidate

    if not job_types_dir.exists():
        logger.warning("job-types directory not found: %s", job_types_dir)
        return {}

    job_types: Dict[str, Any] = {}
    for json_file in sorted(job_types_dir.glob("*.json")):
        try:
            with open(json_file, encoding="utf-8") as fh:
                definition = json.load(fh)

            name = definition.get("name")
            if not name:
                logger.warning("Job type file missing 'name' field: %s", json_file)
                continue

            # Allow env var override of endpoint for service workers
            env_key = f"WORKER_{name.upper().replace('-', '_')}_ENDPOINT"
            env_endpoint = os.getenv(env_key)
            if env_endpoint:
                if "service" in definition:
                    definition["service"]["endpoint"] = env_endpoint
                else:
                    definition["endpoint"] = env_endpoint

            job_types[name] = definition
            logger.debug("Loaded job-type: %s (execution_model=%s)", name, definition.get("execution_model", "service"))
        except Exception as exc:
            logger.error("Failed to load job-type from %s: %s", json_file, exc)

    return job_types


def _build_job_types_config(
    job_types_dir: "Path | None" = None,
) -> Dict[str, Any]:
    """
    Build JOB_TYPES_CONFIG from loaded job-type definitions.

    Aliases are expanded as additional keys so legacy names continue to work.
    """
    loaded = _load_job_types_from_artifacts(job_types_dir)
    config: Dict[str, Any] = {}

    for name, job_type in loaded.items():
        execution_model = job_type.get("execution_model", "service")

        if execution_model == "subprocess":
            entry: Dict[str, Any] = {
                "execution_model": "subprocess",
                "worker_name": Path(job_type.get("worker", {}).get("path", name)).name,
                "worker": job_type.get("worker", {}),
                "configuration": job_type.get("configuration", {}),
                "queue_l1": job_type.get("queue_l1"),
                "queue_l2": job_type.get("queue_l2"),
                "timeout": int(job_type.get("configuration", {}).get("timeout_seconds", 60)),
                "result_storage": job_type.get("result_storage", "rpush_l1"),
                "result_key_prefix": job_type.get("result_key_prefix"),
                "result_key_ttl": int(job_type.get("result_key_ttl", 120)),
                "dependencies": job_type.get("dependencies", []),
            }
        else:
            # Service execution model (default): HTTP routing
            service_cfg = job_type.get("service", {})
            endpoint = service_cfg.get("endpoint") or job_type.get("endpoint")
            entry = {
                "execution_model": "service",
                "worker_name": job_type.get("worker_type", name),
                "service_name": service_cfg.get("name", ""),
                "endpoint": endpoint,
                "health_path": service_cfg.get("health_path", "/health"),
                "queue_l1": job_type.get("queue_l1"),
                "queue_l2": job_type.get("queue_l2"),
                "timeout": int(job_type.get("timeout", 60)),
                "result_storage": job_type.get("result_storage", "rpush_l1"),
                "result_key_prefix": job_type.get("result_key_prefix"),
                "result_key_ttl": int(job_type.get("result_key_ttl", 120)),
                "dependencies": job_type.get("dependencies", []),
            }

        config[name] = entry

        for alias in job_type.get("aliases", []):
            if alias != name:
                config[alias] = entry

    return config


# Load job-types at module init (single source of truth)
JOB_TYPES_CONFIG = _build_job_types_config()

if not JOB_TYPES_CONFIG:
    logger.warning("⚠️ No job-types loaded from artifacts/canonical/job-types/")
    logger.warning("   GateKeeper will start without configured workers")

ALL_QUEUES_L1 = list({
    cfg.get("queue_l1")
    for cfg in JOB_TYPES_CONFIG.values()
    if cfg.get("queue_l1")
})
ALL_QUEUES_L2 = list({
    cfg.get("queue_l2")
    for cfg in JOB_TYPES_CONFIG.values()
    if cfg.get("queue_l2")
})


# ============================================================================
# Module-level __getattr__ – Backward-Compatible Lazy Constant Access
# ============================================================================

def __getattr__(name: str):
    """Intercept module-level attribute access for lazy-loading constants.

    Maps all constant names (REDIS_L1_HOST, CENTRALHUB_URL, etc.) to config
    class methods.  When code accesses a constant, this function resolves it
    lazily via the appropriate config class.

    Resolution order: Redis L1 → SecretClient (vault.*) → os.getenv → default.
    """
    _config_map = {
        # Redis L1
        "REDIS_L1_HOST": RedisL1Config.host,
        "REDIS_L1_PORT": RedisL1Config.port,
        "REDIS_L1_PASSWORD": RedisL1Config.password,
        "REDIS_L1_DB": RedisL1Config.db,
        # CentralHub
        "CENTRALHUB_URL": CentralHubConfig.url,
        "CENTRALHUB_SERVICE_TOKEN": CentralHubConfig.service_token,
        # Queue
        "QUEUE_PRIORITY": QueueConfig.priority,
        "BRPOP_L1_TIMEOUT": QueueConfig.brpop_l1_timeout,
        "BRPOP_L2_TIMEOUT": QueueConfig.brpop_l2_timeout,
        "CPU_JOBS_QUEUE_L1": QueueConfig.cpu_jobs_queue_l1,
        "CPU_JOBS_QUEUE_L2": QueueConfig.cpu_jobs_queue_l2,
        "THREE_D_JOBS_QUEUE_L1": QueueConfig.three_d_jobs_queue_l1,
        "THREE_D_JOBS_QUEUE_L2": QueueConfig.three_d_jobs_queue_l2,
        "DEAD_LETTER_QUEUE": QueueConfig.dead_letter_queue,
        "COMMANDS_QUEUE": QueueConfig.commands_queue,
        # Worker
        "WORKER_ID": WorkerConfig.worker_id,
        "WORKER_HEARTBEAT_INTERVAL": WorkerConfig.heartbeat_interval,
        "WORKER_MAX_RETRIES": WorkerConfig.max_retries,
        "WORKER_RETRY_DELAY": WorkerConfig.retry_delay,
        # Telemetry
        "TELEMETRY_KEY": TelemetryConfig.telemetry_key,
        "TELEMETRY_STALE_AFTER_SECONDS": TelemetryConfig.stale_after_seconds,
        "SCALE_UP_VRAM_MIN_MB": TelemetryConfig.scale_up_vram_min_mb,
        "SCALE_UP_RAM_MIN_MB": TelemetryConfig.scale_up_ram_min_mb,
        "SCALE_UP_QUEUE_DEPTH": TelemetryConfig.scale_up_queue_depth,
        "SCALE_DOWN_IDLE_SECONDS": TelemetryConfig.scale_down_idle_seconds,
        "WORKER_STATE_KEY_PREFIX": TelemetryConfig.worker_state_key_prefix,
        # HTTP
        "HTTP_REQUEST_TIMEOUT": HttpConfig.request_timeout,
        "HTTP_CONNECT_TIMEOUT": HttpConfig.connect_timeout,
        # Health checks
        "VENV_HEALTH_CHECK_INTERVAL": HealthCheckConfig.venv_health_check_interval,
        "SERVICE_HEALTH_PROBE_TIMEOUT": HealthCheckConfig.service_health_probe_timeout,
        # Logging
        "LOG_LEVEL": LoggingConfig.log_level,
        "LOG_FORMAT": LoggingConfig.log_format,
        "LOG_FORMAT_TYPE": LoggingConfig.log_format_type,
        # Job state
        "JOB_STATE_KEY_PREFIX": JobStateConfig.key_prefix,
        "JOB_STATE_TTL_SECONDS": JobStateConfig.ttl_seconds,
    }

    if name in _config_map:
        return _config_map[name]()

    raise AttributeError(f"module 'config' has no attribute '{name}'")
