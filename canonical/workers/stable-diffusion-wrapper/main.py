#!/usr/bin/env python3
"""
Stable Diffusion Wrapper Job Worker – CLI Entry Point.

Subprocess worker that forwards jobs to the SD inference service via HTTP.
Invoked by GateKeeper for "sd_generate" job types.
"""

import json
import sys
import traceback

from worker import StableDiffusionWorker

if __name__ == "__main__":
    try:
        stdin_data = sys.stdin.read()
        if not stdin_data:
            raise ValueError("No input data received on stdin")

        data = json.loads(stdin_data)
        job_id = data.get("job_id", "unknown")

        worker = StableDiffusionWorker(
            job_id=job_id,
            job_type=data.get("job_type", "unknown"),
            input_data=data.get("input_data", {}),
        )
        worker.run()
    except json.JSONDecodeError as exc:
        response = {"success": False, "error": f"Invalid JSON in stdin: {exc}"}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
    except Exception as exc:
        error_msg = f"Worker startup failed: {exc}\n{traceback.format_exc()}"
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
