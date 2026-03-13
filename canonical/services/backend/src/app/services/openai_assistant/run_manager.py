"""
OpenAI Run Manager Module

Handles run execution and polling operations for the OpenAI Assistants API.

Functions:
- run_assistant: Execute a run and wait for completion

Technical naming: All functions and variables in English.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import httpx

from ...config import OPENAI_API_KEY, OPENAI_API_URL, OPENAI_TIMEOUT

logger = logging.getLogger(__name__)

# Default polling interval for run completion (in seconds)
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_MAX_POLL_TIME = 120.0  # 2 minutes max


async def run_assistant(
    thread_id: str,
    assistant_id: str,
    api_key: Optional[str] = None,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    max_poll_time: float = DEFAULT_MAX_POLL_TIME,
) -> Dict[str, Any]:
    """
    Run an assistant on a thread and wait for completion.

    This function creates a run, polls for completion, and returns the final run status.

    Args:
        thread_id: Thread ID to run assistant on
        assistant_id: Assistant ID to use
        api_key: API Key (optional, falls back to config)
        poll_interval: Polling interval in seconds (default: 1.0)
        max_poll_time: Maximum time to poll in seconds (default: 120.0)

    Returns:
        Run object with final status

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPError: If there's an error communicating with OpenAI
        TimeoutError: If run doesn't complete within max_poll_time

    Example:
        >>> run = await run_assistant(
        ...     thread_id="thread_abc123",
        ...     assistant_id="asst_abc123"
        ... )
    """
    effective_api_key = api_key or OPENAI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    logger.info("Running assistant %s on thread %s", assistant_id, thread_id)

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            # Create run
            response = await client.post(
                f"{OPENAI_API_URL}/threads/{thread_id}/runs",
                headers={
                    "Authorization": f"Bearer {effective_api_key}",
                    "Content-Type": "application/json",
                    "OpenAI-Beta": "assistants=v2",
                },
                json={"assistant_id": assistant_id},
            )
            response.raise_for_status()

            run_result = response.json()
            run_id = run_result.get("id")

            if not run_id:
                logger.error("Invalid response from Runs API: %s", run_result)
                raise ValueError("Invalid response from OpenAI Runs API")

            logger.info("Run created: %s", run_id)

            # Poll for completion
            start_time = time.time()
            while True:
                elapsed = time.time() - start_time
                if elapsed > max_poll_time:
                    raise TimeoutError(f"Run did not complete within {max_poll_time}s")

                # Check run status
                status_response = await client.get(
                    f"{OPENAI_API_URL}/threads/{thread_id}/runs/{run_id}",
                    headers={
                        "Authorization": f"Bearer {effective_api_key}",
                        "OpenAI-Beta": "assistants=v2",
                    },
                )
                status_response.raise_for_status()

                run_status = status_response.json()
                status = run_status.get("status")

                logger.debug("Run %s status: %s", run_id, status)

                # Check terminal states
                if status in ["completed", "failed", "cancelled", "expired"]:
                    logger.info("Run %s finished with status: %s", run_id, status)
                    return run_status

                # Continue polling
                await asyncio.sleep(poll_interval)

    except httpx.HTTPError as e:
        logger.error("HTTP error running assistant: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error running assistant: %s", e)
        raise
