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

import sys
from pathlib import Path

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
