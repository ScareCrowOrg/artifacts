#!/usr/bin/env python3
"""
Ollama Wrapper Job Worker – CLI Entry Point.

Subprocess worker that forwards jobs to the Ollama inference service via HTTP.
Invoked by GateKeeper for "ollama_generate" and "ollama_chat" job types.
"""

import json
import sys
import traceback

from worker import OllamaWorker

if __name__ == "__main__":
    try:
        print("🔧 [Ollama-Worker] Starting...", file=sys.stderr)
        stdin_data = sys.stdin.read()
        if not stdin_data:
            raise ValueError("No input data received on stdin")

        print(f"📥 [Ollama-Worker] Received stdin data ({len(stdin_data)} bytes)", file=sys.stderr)
        data = json.loads(stdin_data)
        job_id = data.get("job_id", "unknown")
        print(f"📋 [Ollama-Worker] Job ID: {job_id}", file=sys.stderr)

        worker = OllamaWorker(
            job_id=job_id,
            job_type=data.get("job_type", "unknown"),
            input_data=data.get("input_data", {}),
        )
        print(f"⚙️  [Ollama-Worker] Created worker, calling run()...", file=sys.stderr)
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
