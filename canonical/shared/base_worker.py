"""
BaseWorker – Abstract contract for all subprocess job workers.

Every job worker (Rembg, Ollama-wrapper, SD-wrapper, custom) must
subclass BaseWorker and implement the execute() method.

Communication contract (stdin/stdout JSON):
  stdin:  {"job_id": "...", "job_type": "...", "input_data": {...}}
  stdout: {"success": true, "result": {...}}
          {"success": false, "error": "..."}

Usage:
    class MyWorker(BaseWorker):
        def execute(self) -> Dict[str, Any]:
            return {"output": process(self.input_data)}

    if __name__ == "__main__":
        worker = MyWorker.from_stdin()
        worker.run()
"""

import json
import logging
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseWorker(ABC):
    """
    Abstract base class for all subprocess job workers.

    Subclasses must implement execute(). The run() method orchestrates
    setup → execute → teardown and handles JSON I/O with the GateKeeper.
    """

    def __init__(self, job_id: str, job_type: str, input_data: Dict[str, Any]):
        self.job_id = job_id
        self.job_type = job_type
        self.input_data = input_data
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stderr,
        )
        logger = logging.getLogger(self.__class__.__name__)
        logger.info("[%s] Initializing worker for %s", self.job_id, self.job_type)
        return logger

    def setup(self) -> None:
        """Optional: setup phase (load models, initialize clients)."""

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        Execute the job synchronously.

        Returns:
            Result dict that will be included in {"success": true, "result": <here>}

        Raises:
            Exception: Any exception triggers error response.
        """
        raise NotImplementedError

    def teardown(self) -> None:
        """Optional: cleanup phase (unload models, close connections)."""

    def run(self) -> None:
        """
        Orchestrate setup → execute → teardown with JSON I/O.

        Reads job data from self (already set by from_stdin()).
        Writes result JSON to stdout.
        Exits 0 on success, 1 on error.
        """
        try:
            self.setup()
            result = self.execute()
            self.teardown()
            response = {"success": True, "result": result}
            print(json.dumps(response), file=sys.stdout)
            sys.exit(0)
        except Exception as exc:
            self.logger.error("[%s] Job failed: %s", self.job_id, exc, exc_info=True)
            try:
                self.teardown()
            except Exception:
                pass
            response = {"success": False, "error": str(exc)}
            print(json.dumps(response), file=sys.stdout)
            sys.exit(1)

    @classmethod
    def from_stdin(cls) -> "BaseWorker":
        """
        Factory: create worker instance from JSON read via stdin.

        Expected stdin format:
            {"job_id": "...", "job_type": "...", "input_data": {...}}
        """
        raw = sys.stdin.read()
        data = json.loads(raw)
        return cls(
            job_id=data["job_id"],
            job_type=data["job_type"],
            input_data=data["input_data"],
        )
