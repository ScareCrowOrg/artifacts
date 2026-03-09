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

from worker import RembgWorker

if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.read())
        worker = RembgWorker(
            job_id=data["job_id"],
            job_type=data["job_type"],
            input_data=data["input_data"],
        )
        worker.run()
    except Exception as exc:
        response = {"success": False, "error": f"Worker startup failed: {exc}"}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
