#!/usr/bin/env python3
"""
ComfyUI Wrapper Job Worker – CLI Entry Point.

Subprocess worker that forwards jobs to the ComfyUI inference service via HTTP.
Invoked by GateKeeper for "comfyui_generate" job types.
"""

import json
import sys
import traceback

from worker import ComfyUIWorker

if __name__ == "__main__":
    try:
        print("🔧 [ComfyUI-Worker] Starting...", file=sys.stderr)
        stdin_data = sys.stdin.read()
        if not stdin_data:
            raise ValueError("No input data received on stdin")

        print(f"📥 [ComfyUI-Worker] Received stdin data ({len(stdin_data)} bytes)", file=sys.stderr)
        data = json.loads(stdin_data)
        job_id = data.get("job_id", "unknown")
        print(f"📋 [ComfyUI-Worker] Job ID: {job_id}", file=sys.stderr)

        worker = ComfyUIWorker(
            job_id=job_id,
            job_type=data.get("job_type", "unknown"),
            input_data=data.get("input_data", {}),
        )
        print(f"⚙️  [ComfyUI-Worker] Created worker, calling run()...", file=sys.stderr)
        worker.run()

    except json.JSONDecodeError as exc:
        error_msg = f"Invalid JSON in stdin: {exc}"
        print(f"❌ [ComfyUI-Worker] {error_msg}", file=sys.stderr)
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
    except Exception as exc:
        error_msg = f"Worker startup/execution failed: {exc}\n{traceback.format_exc()}"
        print(f"❌ [ComfyUI-Worker] {error_msg}", file=sys.stderr)
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
