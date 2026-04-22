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
        print("🔧 [SD-Worker] Starting...", file=sys.stderr)
        stdin_data = sys.stdin.read()
        if not stdin_data:
            raise ValueError("No input data received on stdin")

        print(f"📥 [SD-Worker] Received stdin data ({len(stdin_data)} bytes)", file=sys.stderr)
        data = json.loads(stdin_data)
        job_id = data.get("job_id", "unknown")
        print(f"📋 [SD-Worker] Job ID: {job_id}", file=sys.stderr)

        worker = StableDiffusionWorker(
            job_id=job_id,
            job_type=data.get("job_type", "unknown"),
            input_data=data.get("input_data", {}),
        )
        print(f"⚙️  [SD-Worker] Created worker, calling run()...", file=sys.stderr)
        worker.run()
        # Note: worker.run() calls sys.exit(), so code below won't execute

    except json.JSONDecodeError as exc:
        error_msg = f"Invalid JSON in stdin: {exc}"
        print(f"❌ [SD-Worker] {error_msg}", file=sys.stderr)
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
    except Exception as exc:
        error_msg = f"Worker startup/execution failed: {exc}\n{traceback.format_exc()}"
        print(f"❌ [SD-Worker] {error_msg}", file=sys.stderr)
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
