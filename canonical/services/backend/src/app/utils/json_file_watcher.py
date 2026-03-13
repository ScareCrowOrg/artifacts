"""
JSON File Watcher for development hot reload.

Monitors changes in canonical JSON files (notebook_item_types, ai_models, etc)
and provides a mechanism to reload them without restarting the backend.

Useful for data-driven development where configuration is stored in JSON.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Set

logger = logging.getLogger(__name__)


class JSONFileWatcher:
    """
    Monitors JSON files for changes and triggers reload callbacks.

    Usage:
        watcher = JSONFileWatcher()
        watcher.watch_directory(
            directory=Path("artifacts/canonical/notebook_item_types"),
            on_change=my_reload_function
        )
        await watcher.start()
    """

    def __init__(self):
        self.watchers: Dict[str, Dict] = {}
        self.last_modified: Dict[str, float] = {}
        self.running = False
        self.monitor_task = None

    def watch_directory(
        self,
        directory: Path,
        pattern: str = "*.json",
        on_change: Callable = None,
        debounce_ms: int = 500,
    ):
        """
        Register a directory to watch for JSON changes.

        Args:
            directory: Path to directory to watch
            pattern: File pattern to match (default: *.json)
            on_change: Async callback function called when files change
            debounce_ms: Debounce delay to avoid multiple triggers
        """
        watch_id = str(directory)
        self.watchers[watch_id] = {
            "directory": directory,
            "pattern": pattern,
            "on_change": on_change,
            "debounce_ms": debounce_ms,
            "last_trigger": 0,
        }
        logger.info("📁 Watching directory: %s (pattern: %s)", directory, pattern)

    async def start(self):
        """Start monitoring files."""
        if self.running:
            logger.warning("File watcher already running")
            return

        self.running = True
        logger.info("🔍 Starting JSON file watcher for development hot reload")

        # Start the monitor loop
        self.monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stop monitoring files."""
        self.running = False
        if self.monitor_task:
            await self.monitor_task
        logger.info("⏹️  JSON file watcher stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                for watch_id, config in self.watchers.items():
                    await self._check_directory(watch_id, config)
            except Exception as e:
                logger.error("Error in file watcher: %s", e)

            # Check every 1 second
            await asyncio.sleep(1)

    async def _check_directory(self, _watch_id: str, config: Dict):
        """Check a directory for changed files."""
        directory = config["directory"]
        pattern = config["pattern"]
        on_change = config["on_change"]
        debounce_ms = config["debounce_ms"]

        if not directory.exists():
            return

        # Find all matching files
        changed_files: Set[Path] = set()

        for file_path in directory.glob(pattern):
            if not file_path.is_file():
                continue

            try:
                stat = file_path.stat()
                current_mtime = stat.st_mtime
                file_key = str(file_path)
                last_mtime = self.last_modified.get(file_key, 0)

                # File was modified
                if current_mtime > last_mtime:
                    self.last_modified[file_key] = current_mtime
                    changed_files.add(file_path)
                    logger.debug("📝 File changed: %s", file_path.name)

            except Exception as e:
                logger.error("Error checking file %s: %s", file_path, e)

        # Trigger callback if files changed
        if changed_files and on_change:
            now = datetime.now().timestamp() * 1000  # ms
            last_trigger = config.get("last_trigger", 0)

            # Debounce: only trigger if enough time has passed
            if now - last_trigger > debounce_ms:
                config["last_trigger"] = now

                try:
                    logger.info("🔄 Reloading %s changed file(s)...", len(changed_files))

                    # Call the callback
                    if asyncio.iscoroutinefunction(on_change):
                        await on_change(changed_files)
                    else:
                        on_change(changed_files)

                    logger.info("✅ Reload complete")

                except Exception as e:
                    logger.error("Error in file change callback: %s", e)


# Global watcher instance
_watcher: JSONFileWatcher = None


def get_watcher() -> JSONFileWatcher:
    """Get or create the global watcher instance."""
    global _watcher
    if _watcher is None:
        _watcher = JSONFileWatcher()
    return _watcher


async def start_watchers():
    """Start all registered watchers."""
    watcher = get_watcher()
    await watcher.start()


async def stop_watchers():
    """Stop all watchers."""
    watcher = get_watcher()
    await watcher.stop()
