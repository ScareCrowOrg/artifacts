"""
Root conftest for the GateKeeper service tests.

GateKeeper modules (config.py, pooling.py, main.py) use bare module imports
(e.g. ``import config``) because they are run as scripts inside the Docker
container.  When executing tests via pytest using package-relative imports
(``from ..main import GateKeeper``) those bare imports fail unless:

  1. The gatekeeper package directory is on sys.path so that bare imports
     like ``import config`` succeed at all, AND
  2. The bare module objects (``sys.modules['config']``) are aliased under
     their fully-qualified package names (``sys.modules['gatekeeper.config']``)
     so that ``patch.object(config, ...)`` in test code patches the same object
     that GateKeeper internals reference.

This conftest handles both concerns before any test module is collected.
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Pre-seed config env vars so that lazy config lookups in modules imported
# below (especially main.py) bypass Redis and resolve instantly.  These
# defaults are safe for testing; real values come from Redis at runtime.
# ---------------------------------------------------------------------------
_TEST_ENV_DEFAULTS = {
    "LOG_LEVEL": "WARNING",
    "LOG_FORMAT": "%(message)s",
    "LOG_FORMAT_TYPE": "text",
    "COMMANDS_QUEUE": "commands:gatekeeper:queue",
    "WORKER_STATE_KEY_PREFIX": "state:worker",
    "TELEMETRY_KEY": "state:host:telemetry",
    "SCALE_UP_VRAM_MIN_MB": "4096",
    "SCALE_UP_RAM_MIN_MB": "4096",
    "SCALE_UP_QUEUE_DEPTH": "3",
    "SCALE_DOWN_IDLE_SECONDS": "300",
    "CPU_JOBS_QUEUE_L1": "scareverse:cpu-jobs:queue",
    "CPU_JOBS_QUEUE_L2": "scareverse:cpu-jobs:queue",
    "THREE_D_JOBS_QUEUE_L1": "scareverse:3d-jobs:queue",
    "THREE_D_JOBS_QUEUE_L2": "scareverse:3d-jobs:queue",
    "DEAD_LETTER_QUEUE": "scareverse:dead-letter:queue",
    "BRPOP_L1_TIMEOUT": "5",
    "BRPOP_L2_TIMEOUT": "10",
    "QUEUE_PRIORITY": "l1",
    "WORKER_ID": "gatekeeper-test",
    "WORKER_HEARTBEAT_INTERVAL": "30",
    "WORKER_MAX_RETRIES": "3",
    "WORKER_RETRY_DELAY": "5",
    "TELEMETRY_STALE_AFTER_SECONDS": "30",
    "VENV_HEALTH_CHECK_INTERVAL": "60",
    "HTTP_REQUEST_TIMEOUT": "30",
    "HTTP_CONNECT_TIMEOUT": "5",
    "JOB_STATE_TTL_SECONDS": "3600",
}
for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)

# ---------------------------------------------------------------------------
# Disable Redis in config_manager so lazy config lookups complete instantly
# (via the env-var fallback above) without any connection attempt.
# redis-py 7.x has retry logic that can add 8+ seconds per lookup.
# ---------------------------------------------------------------------------
try:
    import artifacts.shared.config_manager as _cm
    _cm._get_redis_client = lambda: None  # type: ignore[attr-defined]
except Exception:
    pass  # Not available in all test environments; env-var fallback still works.

# --- Step 1: add the gatekeeper directory to sys.path ---------------------------
_GATEKEEPER_DIR = str(Path(__file__).parent)
if _GATEKEEPER_DIR not in sys.path:
    sys.path.insert(0, _GATEKEEPER_DIR)

# --- Step 2: pre-import bare modules and alias under the package namespace ------
_BARE_MODULES = ("config", "pooling", "orchestrator", "job_executor", "service_executor", "worker_discovery", "main")
for _mod in _BARE_MODULES:
    if _mod not in sys.modules:
        import importlib
        importlib.import_module(_mod)
    _pkg_name = f"gatekeeper.{_mod}"
    if _pkg_name not in sys.modules:
        sys.modules[_pkg_name] = sys.modules[_mod]
