"""
TEMPLATE Worker – BaseWorker implementation.

Copy this file, rename the class (e.g. MyCustomWorker), and implement:
  - setup()    – optional: load models, open connections
  - execute()  – REQUIRED: perform the job, return result dict
  - teardown() – optional: close connections, release resources
"""

import sys
from pathlib import Path
from typing import Any, Dict

# Allow importing shared BaseWorker both when running from GateKeeper
# (PYTHONPATH=/app/artifacts) and when running tests directly.
try:
    from canonical.shared.base_worker import BaseWorker
except ImportError:
    _canonical_parent = Path(__file__).resolve().parents[2].parent
    if str(_canonical_parent) not in sys.path:
        sys.path.insert(0, str(_canonical_parent))
    from canonical.shared.base_worker import BaseWorker


class TemplateWorker(BaseWorker):
    """
    Template worker – replace this docstring with your worker description.

    input_data keys:
        - example_field (str): Description of expected input.

    result keys:
        - output (str): Description of output.
    """

    def setup(self) -> None:
        """Load models or open connections here (called once before execute)."""
        # Example:
        # self.model = load_model(...)
        self.logger.info("Setup complete")

    def execute(self) -> Dict[str, Any]:
        """
        Perform the job.

        Returns:
            A dict that will be wrapped in {"success": true, "result": <dict>}
            and returned to GateKeeper.

        Raises:
            ValueError: On invalid input.
            Exception: On processing errors.
        """
        # ----------------------------------------------------------------
        # 1. Validate input
        # ----------------------------------------------------------------
        example_field = self.input_data.get("example_field")
        if not example_field:
            raise ValueError("Missing required field: example_field")

        # ----------------------------------------------------------------
        # 2. Perform work
        # ----------------------------------------------------------------
        self.logger.info("Processing job %s", self.job_id)
        output = f"Processed: {example_field}"

        # ----------------------------------------------------------------
        # 3. Return result dict
        # ----------------------------------------------------------------
        return {"output": output}

    def teardown(self) -> None:
        """Release resources here (always called, even on failure)."""
        # Example:
        # if hasattr(self, 'model'):
        #     del self.model
        pass
