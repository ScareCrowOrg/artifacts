#!/usr/bin/env python3
"""
TEMPLATE Worker – CLI Entry Point.

Subprocess worker invoked by GateKeeper:

    .venv/bin/python main.py
    stdin:  {"job_id": "...", "job_type": "template_job", "input_data": {...}}
    stdout: {"success": true, "result": {...}}
            {"success": false, "error": "..."}

Copy this file and rename it.  No changes to main.py are needed unless you
need to pre-process stdin before constructing the worker.
"""

import json
import sys

from worker import TemplateWorker

if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.read())
        worker = TemplateWorker(
            job_id=data["job_id"],
            job_type=data["job_type"],
            input_data=data["input_data"],
        )
        worker.run()
    except Exception as exc:
        response = {"success": False, "error": f"Worker startup failed: {exc}"}
        print(json.dumps(response), file=sys.stdout)
        sys.exit(1)
