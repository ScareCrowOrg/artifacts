#!/usr/bin/env python3
"""
ComfyUI Hunyuan3D Job Worker – CLI Entry Point.

Subprocess worker that forwards 3D mesh generation jobs to the ComfyUI
inference service via HTTP. Invoked by GateKeeper for "hunyuan3d_generate"
job types.
"""

import json
import sys
import traceback

from worker import Hunyuan3DWorker

if __name__ == "__main__":
    try:
        print(" [Hunyuan3D-Worker] Starting...", file=sys.stderr)
        stdin_data = sys.stdin.read()
        if not stdin_data:
            raise ValueError("No input data received on stdin")

        print(
            f" [Hunyuan3D-Worker] Received stdin data ({len(stdin_data)} bytes)",
            file=sys.stderr,
        )
        data = json.loads(stdin_data)
        job_id = data.get("job_id", "unknown")
        print(f" [Hunyuan3D-Worker] Job ID: {job_id}", file=sys.stderr)

        worker = Hunyuan3DWorker(
            job_id=job_id,
            job_type=data.get("job_type", "unknown"),
            input_data=data.get("input_data", {}),
        )
        print(f" [Hunyuan3D-Worker] Created worker, calling run()...", file=sys.stderr)
        worker.run()

    except json.JSONDecodeError as exc:
        error_msg = f"Invalid JSON in stdin: {exc}"
        print(f" [Hunyuan3D-Worker] {error_msg}", file=sys.stderr)
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
    except Exception as exc:
        error_msg = f"Worker startup/execution failed: {exc}\n{traceback.format_exc()}"
        print(f" [Hunyuan3D-Worker] {error_msg}", file=sys.stderr)
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
