"""
ServiceExecutor – HTTP routing for GateKeeper Service.

Routes jobs to long-lived service workers (Ollama, Stable Diffusion, etc.)
via HTTP POST. This is the pre-existing execution model, extracted into its
own module to complement the new subprocess model in job_executor.py.
"""

import logging
from typing import Any, Dict

import httpx

import config

logger = logging.getLogger(__name__)


class ServiceExecutor:
    """
    Dispatches jobs to service workers via HTTP POST.

    Handles retry logic with exponential back-off and dead-letter fallback.
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self._http = http_client

    async def execute(
        self,
        job_type: str,
        job_id: str,
        job_payload: Dict[str, Any],
        job_type_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        POST job to service endpoint and return the parsed response body.

        Args:
            job_type: Job type name.
            job_id: Unique job identifier.
            job_payload: Full job dict forwarded to the worker.
            job_type_config: Entry from JOB_TYPES_CONFIG with ``execution_model == "service"``.

        Returns:
            Parsed JSON response from the worker.

        Raises:
            Exception: After max retries are exhausted or on permanent failure.
        """
        # Build endpoint: base URL + optional path suffix (default: /process)
        base_endpoint = job_type_config['endpoint']
        endpoint_path = job_type_config.get('endpoint_path', '/process')
        endpoint = f"{base_endpoint}{endpoint_path}"
        timeout = job_type_config.get("timeout", config.HTTP_REQUEST_TIMEOUT)
        retries = 0

        while retries <= config.WORKER_MAX_RETRIES:
            try:
                response = await self._http.post(
                    endpoint,
                    json=job_payload,
                    timeout=httpx.Timeout(timeout, connect=config.HTTP_CONNECT_TIMEOUT),
                )

                if response.status_code == 200:
                    logger.info("[%s] Service worker responded 200 OK", job_id)
                    return response.json()

                if 400 <= response.status_code < 500:
                    raise ValueError(
                        f"Permanent failure HTTP {response.status_code}: {response.text[:300]}"
                    )

                logger.warning(
                    "[%s] Service worker HTTP %d – retry %d/%d",
                    job_id,
                    response.status_code,
                    retries,
                    config.WORKER_MAX_RETRIES,
                )

            except httpx.TimeoutException:
                logger.warning(
                    "[%s] Service worker timed out (retry %d/%d)",
                    job_id,
                    retries,
                    config.WORKER_MAX_RETRIES,
                )
            except httpx.ConnectError as exc:
                logger.warning(
                    "[%s] Cannot reach service worker %s (retry %d/%d): %s",
                    job_id,
                    endpoint,
                    retries,
                    config.WORKER_MAX_RETRIES,
                    exc,
                )

            retries += 1
            if retries <= config.WORKER_MAX_RETRIES:
                import asyncio
                delay = min(config.WORKER_RETRY_DELAY * (2 ** (retries - 1)), 60.0)
                await asyncio.sleep(delay)

        raise RuntimeError(
            f"Job {job_id} exceeded max retries ({config.WORKER_MAX_RETRIES}) for endpoint {endpoint}"
        )
