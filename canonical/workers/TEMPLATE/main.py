#!/usr/bin/env python3
"""
TEMPLATE Worker – CLI Entry Point.

Subprocess worker invoked by GateKeeper:

    .venv/bin/python main.py
    stdin:  {"job_id": "...", "job_type": "template_job", "input_data": {...}}
    stdout: {"success": true, "result": {...}}
            {"success": false, "error": "..."}
    stderr: Diagnostic logs (print to stderr for parent process capture)

Copy this file and rename it. Logs should go to stderr so they appear in parent
process (GateKeeper) logs. Result JSON goes to stdout only.
"""

import json
import sys
import traceback

from worker import TemplateWorker

if __name__ == "__main__":
    try:
        print("🔧 [Template-Worker] Starting...", file=sys.stderr)
        stdin_data = sys.stdin.read()
        if not stdin_data:
            raise ValueError("No input data received on stdin")

        print(f"📥 [Template-Worker] Received stdin data ({len(stdin_data)} bytes)", file=sys.stderr)
        data = json.loads(stdin_data)
        job_id = data.get("job_id", "unknown")
        print(f"📋 [Template-Worker] Job ID: {job_id}", file=sys.stderr)

        worker = TemplateWorker(
            job_id=job_id,
            job_type=data.get("job_type", "unknown"),
            input_data=data.get("input_data", {}),
        )
        print(f"⚙️  [Template-Worker] Created worker, calling run()...", file=sys.stderr)
        worker.run()
    except json.JSONDecodeError as exc:
        error_msg = f"Invalid JSON in stdin: {exc}"
        print(f"❌ [Template-Worker] {error_msg}", file=sys.stderr)
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
    except Exception as exc:
        error_msg = f"Worker startup failed: {exc}\n{traceback.format_exc()}"
        print(f"❌ [Template-Worker] {error_msg}", file=sys.stderr)
        response = {"success": False, "error": error_msg}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
