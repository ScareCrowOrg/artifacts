#!/usr/bin/env python3
"""
Stable Diffusion Wrapper Job Worker – CLI Entry Point.

Subprocess worker that forwards jobs to the SD inference service via HTTP.
Invoked by GateKeeper for "sd_generate" job types.
"""

import json
import sys

from worker import StableDiffusionWorker

if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.read())
        worker = StableDiffusionWorker(
            job_id=data["job_id"],
            job_type=data["job_type"],
            input_data=data["input_data"],
        )
        worker.run()
    except Exception as exc:
        response = {"success": False, "error": f"Worker startup failed: {exc}"}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
