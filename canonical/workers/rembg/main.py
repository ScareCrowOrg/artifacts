#!/usr/bin/env python3
"""
Rembg Job Worker – CLI Entry Point.

Subprocess worker for background removal. Invoked by GateKeeper:

    venv/bin/python main.py
    stdin:  {"job_id": "...", "job_type": "rembg_removebackground", "input_data": {...}}
    stdout: {"success": true, "result": {"image_base64": "..."}}
            {"success": false, "error": "..."}
"""

import json
import sys
import traceback
import time

from worker import RembgWorker

if __name__ == "__main__":
    try:
        print("🔧 [Rembg-Worker] Starting...", file=sys.stderr)
        start_time = time.time()

        stdin_read_start = time.time()
        stdin_data = sys.stdin.read()
        stdin_read_elapsed = time.time() - stdin_read_start

        if not stdin_data:
            raise ValueError("No input data received on stdin")

        print(f"📥 [Rembg-Worker] Read stdin in {stdin_read_elapsed:.3f}s ({len(stdin_data)} bytes)", file=sys.stderr)

        parse_start = time.time()
        data = json.loads(stdin_data)
        parse_elapsed = time.time() - parse_start
        job_id = data.get("job_id", "unknown")

        print(f"📋 [Rembg-Worker] Parsed JSON in {parse_elapsed:.3f}s – Job ID: {job_id}", file=sys.stderr)

        print(f"⚙️  [Rembg-Worker] Creating worker for job {job_id}...", file=sys.stderr)
        worker_create_start = time.time()

        worker = RembgWorker(
            job_id=job_id,
            job_type=data.get("job_type", "unknown"),
            input_data=data.get("input_data", {}),
        )

        worker_create_elapsed = time.time() - worker_create_start
        print(f"⏱️  [Rembg-Worker] Worker created in {worker_create_elapsed:.3f}s, calling run()...", file=sys.stderr)

        exec_start = time.time()
        worker.run()
        exec_elapsed = time.time() - exec_start

        total_elapsed = time.time() - start_time
        print(f"✅ [Rembg-Worker] Completed in {exec_elapsed:.3f}s (total: {total_elapsed:.3f}s)", file=sys.stderr)

    except json.JSONDecodeError as exc:
        error_msg = f"Invalid JSON in stdin: {exc}"
        print(f"❌ [Rembg-Worker] {error_msg}", file=sys.stderr)
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
    except Exception as exc:
        error_msg = f"Worker startup failed: {exc}\n{traceback.format_exc()}"
        print(f"❌ [Rembg-Worker] {error_msg}", file=sys.stderr)
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
