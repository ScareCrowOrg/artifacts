"""
Gemini CLI Session Manager
Maintains persistent bash shell and executes gemini -p for each prompt
Zero cold start via persistent shell, fast gemini execution in headless mode
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class GeminiSession:
    """Manages persistent bash shell with gemini CLI execution"""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.shell: Optional[asyncio.subprocess.Process] = None
        self.lock = asyncio.Lock()

        self.prompts_processed = 0
        self.total_input_chars = 0
        self.total_output_chars = 0
        self.start_time = None
        self.last_error: Optional[str] = None
        self.initialized = False

    async def initialize(self):
        """Start persistent bash shell"""
        logger.info("🚀 Starting persistent bash shell...")

        env = os.environ.copy()
        env["GEMINI_API_KEY"] = self.api_key
        env["PYTHONUNBUFFERED"] = "1"  # KEY: unbuffered output

        try:
            logger.info("📦 Spawning bash shell...")
            self.shell = await asyncio.create_subprocess_exec(
                "bash",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )

            logger.info("✅ Shell started (PID=%s)", self.shell.pid)
            self.start_time = time.time()
            self.initialized = True
            logger.info("✅ Session ready (zero cold start)")

        except FileNotFoundError as e:
            logger.error("❌ bash not found")
            raise RuntimeError("bash not found") from e
        except Exception as e:
            logger.error("❌ Failed to start: %s", e)
            raise

    async def send_prompt(self, prompt: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute gemini -p in persistent shell"""

        if not self.initialized:
            logger.warning("Shell not ready, initializing...")
            try:
                await self.initialize()
            except Exception as e:
                return {"status": "error", "error": str(e)}

        logger.info("📨 Prompt queued (len=%s)", len(prompt))

        async with self.lock:
            try:
                start = time.time()
                logger.info("📤 Executing gemini...")

                response = await asyncio.wait_for(
                    self._send_prompt_internal(prompt), timeout=timeout
                )

                elapsed = max(0, time.time() - start)
                self.prompts_processed += 1
                self.total_input_chars += len(prompt)
                self.total_output_chars += len(response)

                logger.info("✅ Response in %ss (%s chars)", elapsed, len(response))

                return {
                    "status": "success",
                    "response": response,
                    "metadata": {
                        "elapsed_time": round(elapsed, 2),
                        "prompts_processed": self.prompts_processed,
                        "input_length": len(prompt),
                        "output_length": len(response),
                    },
                }

            except asyncio.TimeoutError:
                logger.error("⏱️ Timeout after %ss", timeout)
                self.last_error = f"Timeout after {timeout}s"
                return {"status": "error", "error": f"Timeout after {timeout}s"}
            except Exception as e:
                logger.error("❌ Error: %s", e)
                self.last_error = str(e)
                return {"status": "error", "error": str(e)}

    async def _send_prompt_internal(self, prompt: str) -> str:
        """Execute gemini -p in persistent shell, capture response"""

        if not self.shell or not self.shell.stdin or not self.shell.stdout:
            raise RuntimeError("Shell not initialized")

        # Escape single quotes for shell safety
        escaped_prompt = prompt.replace("'", "'\\''")

        # Command: run gemini -p with delimiter for response detection
        cmd = f"gemini -p '{escaped_prompt}' -m {self.model} --yolo; echo '---RESPONSE_END---'\n"

        logger.info("✅ Writing command to shell...")
        self.shell.stdin.write(cmd.encode("utf-8"))
        await self.shell.stdin.drain()

        logger.info("📖 Reading response...")
        response_text = ""
        last_read_time = time.time()
        timeout_seconds = 20

        # Read until delimiter found or timeout
        while True:
            try:
                line = await asyncio.wait_for(
                    self.shell.stdout.readline(),
                    timeout=2.0,  # Short timeout per line
                )
            except asyncio.TimeoutError:
                # Check if we got delimiter already
                if "---RESPONSE_END---" in response_text:
                    break
                # Check overall timeout
                if time.time() - last_read_time > timeout_seconds:
                    logger.error("⏱️ Overall timeout")
                    raise RuntimeError("Timeout reading response")
                continue

            if not line:
                break

            response_text += line.decode("utf-8", errors="replace")
            last_read_time = time.time()

            if "---RESPONSE_END---" in response_text:
                logger.info("✅ Delimiter found")
                break

        # Extract content before delimiter
        if "---RESPONSE_END---" in response_text:
            result = response_text.split("---RESPONSE_END---")[0].strip()
        else:
            result = response_text.strip()

        # Filter out Gemini CLI boilerplate
        lines = result.split("\n")
        filtered_lines = [
            line
            for line in lines
            if line.strip()
            and not any(
                skip in line
                for skip in [
                    "YOLO mode is enabled",
                    "Hook registry initialized",
                    "All tool calls will be automatically approved",
                ]
            )
        ]
        result = "\n".join(filtered_lines).strip()

        logger.info("✅ Response: %s chars", len(result))
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        uptime = time.time() - self.start_time if self.start_time else 0

        return {
            "initialized": self.initialized,
            "uptime_seconds": round(uptime, 2),
            "prompts_processed": self.prompts_processed,
            "total_input_chars": self.total_input_chars,
            "total_output_chars": self.total_output_chars,
            "lock_acquired": self.lock.locked(),
            "last_error": self.last_error,
            "model": self.model,
        }

    async def shutdown(self):
        """Shutdown shell"""
        logger.info("🛑 Shutting down...")
        if self.shell:
            self.shell.terminate()
            try:
                await asyncio.wait_for(self.shell.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.shell.kill()
        self.initialized = False
        logger.info("✅ Shutdown complete")
