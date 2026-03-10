"""
Worker discovery and status tracking for GateKeeper.

Scans the workers/ directory on startup to enumerate available subprocess
workers, logs their status (venv presence, requirements), and provides
a queryable registry for the job dispatcher.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class WorkerDiscovery:
    """
    Discover and track subprocess job workers available to GateKeeper.

    Workers are expected to live in subdirectories of ``workers_path``,
    each containing at minimum a ``main.py`` entry point.  Directories
    whose names start with ``_`` (e.g. ``__pycache__``) are ignored, as
    are non-directory entries.

    Example workers/ layout::

        workers/
        ├── rembg/
        │   ├── main.py
        │   ├── requirements.txt
        │   └── .venv/          ← created on first execution
        ├── ollama-wrapper/
        │   ├── main.py
        │   └── requirements.txt
        └── stable-diffusion-wrapper/
            ├── main.py
            └── requirements.txt
    """

    def __init__(self, workers_path: "str | Path"):
        self.workers_path = Path(workers_path)
        self.discovered_workers: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> Dict[str, dict]:
        """
        Scan workers/ directory and return a metadata dict keyed by worker name.

        Returns:
            Mapping of ``worker_name`` → worker metadata dict containing:
              - ``name``: worker directory name
              - ``path``: absolute path to worker directory (str)
              - ``has_requirements``: whether requirements.txt exists
              - ``has_venv``: whether .venv/ exists (created on first job)
              - ``entry_point``: entry point filename (always ``"main.py"``)
        """
        workers: Dict[str, dict] = {}

        if not self.workers_path.exists():
            logger.warning(
                "Workers path does not exist: %s – no workers discovered",
                self.workers_path,
            )
            self.discovered_workers = workers
            return workers

        for worker_dir in sorted(self.workers_path.iterdir()):
            if not worker_dir.is_dir() or worker_dir.name.startswith("_"):
                continue

            worker_name = worker_dir.name
            main_py = worker_dir / "main.py"
            requirements = worker_dir / "requirements.txt"

            if not main_py.exists():
                logger.debug(
                    "Skipping %s: no main.py found", worker_name
                )
                continue

            metadata = {
                "name": worker_name,
                "path": str(worker_dir),
                "has_requirements": requirements.exists(),
                "has_venv": (worker_dir / ".venv").exists(),
                "entry_point": "main.py",
            }
            workers[worker_name] = metadata
            logger.info("✅ Discovered worker: %s", worker_name)

        self.discovered_workers = workers
        return workers

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self, worker_name: str) -> Optional[dict]:
        """
        Return cached metadata for a specific worker, or None if not found.

        Args:
            worker_name: Name of the worker directory.

        Returns:
            Worker metadata dict or ``None``.
        """
        return self.discovered_workers.get(worker_name)

    def is_available(self, worker_name: str) -> bool:
        """Return True if the worker has been discovered (main.py present)."""
        return worker_name in self.discovered_workers

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_summary(self) -> None:
        """Log a human-readable summary of all discovered workers."""
        if not self.discovered_workers:
            logger.warning("⚠️  No workers discovered in: %s", self.workers_path)
            return

        logger.info(
            "🎯 Worker Discovery Summary: %d worker(s) found in %s",
            len(self.discovered_workers),
            self.workers_path,
        )
        for name, info in self.discovered_workers.items():
            venv_status = "✅ .venv ready" if info["has_venv"] else "⏳ .venv pending (auto-created on first job)"
            req_status = "📋 requirements.txt" if info["has_requirements"] else "⚠️  no requirements.txt"
            logger.info("  ├─ %s: %s | %s", name, venv_status, req_status)
