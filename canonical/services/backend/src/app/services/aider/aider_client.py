"""
Client for communicating with Aider-Worker service.

Backend Core uses this client to interact with the isolated Aider-Worker microservice.
"""

import logging
import os
import socket
from typing import AsyncIterator, List, Optional

import httpx

logger = logging.getLogger(__name__)


class AiderWorkerClient:
    """
    HTTP client for Aider-Worker service communication.

    Handles session creation, command sending, and session termination
    with the isolated Aider-Worker microservice.
    """

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize client with Aider-Worker base URL.

        Args:
            base_url: Base URL of Aider-Worker service.
                     Defaults to AIDER_WORKER_URL env var or http://scareverse-aider-worker:8001
        """
        # DEBUG LOG [ITERATION_1]: Configuration detection
        env_url = os.getenv("AIDER_WORKER_URL")
        logger.debug(
            "[DEBUG][ITERATION_1] AiderWorkerClient initialization - "
            f"AIDER_WORKER_URL env var: {env_url if env_url else 'NOT SET (using default)'}"
        )

        self.base_url = base_url or os.getenv(
            "AIDER_WORKER_URL", "http://scareverse-aider-worker:8001"
        )
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 minutes timeout

        logger.info("Initialized AiderWorkerClient with base URL: %s", self.base_url)

        # DEBUG LOG [ITERATION_1]: Parse hostname for DNS checks
        try:
            from urllib.parse import urlparse

            parsed = urlparse(self.base_url)
            hostname = parsed.hostname
            port = parsed.port or 8001

            logger.debug(
                "[DEBUG][ITERATION_1] Parsed connection details - "
                f"hostname: {hostname}, port: {port}, scheme: {parsed.scheme}"
            )

            # Try to resolve hostname immediately to detect issues early
            try:
                addr_info = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
                resolved_ips = [addr[4][0] for addr in addr_info]
                logger.debug(
                    "[DEBUG][ITERATION_1] DNS resolution successful - hostname '%s' resolves to: %s",
                    hostname, resolved_ips
                )
            except socket.gaierror as dns_err:
                logger.error("[DEBUG][ITERATION_1] ❌ DNS RESOLUTION FAILED during init - hostname '%s' cannot be resolved: %s (errno: %s)", hostname, dns_err, dns_err.errno if hasattr(dns_err, 'errno') else 'N/A')
                logger.error(
                    "[DEBUG][ITERATION_1] This indicates the Aider-Worker service "
                    "is not reachable via DNS. Check: 1) Service is deployed, "
                    "2) Service name is correct, 3) DNS service is running"
                )
            except Exception as resolve_err:
                logger.warning("[DEBUG][ITERATION_1] Could not pre-check DNS resolution: %s", resolve_err)
        except Exception as parse_err:
            logger.warning("[DEBUG][ITERATION_1] Could not parse base_url for DNS pre-check: %s", parse_err)

    async def create_session(
        self, conversation_id: str, files: List[str], model: str = "ollama/qwen2.5-coder:14b"
    ) -> dict:
        """
        Create new Aider session in the worker.

        Args:
            conversation_id: Unique identifier for the session
            files: List of file paths to include in Aider context
            model: LLM model to use for code generation

        Returns:
            Session creation response with status and repository_map_loaded flag

        Raises:
            httpx.HTTPStatusError: If session creation fails
        """
        # DEBUG LOG [ITERATION_1]: Pre-request state
        logger.debug(
            "[DEBUG][ITERATION_1] create_session called - conversation_id: %s, files_count: %s, model: %s",
            conversation_id, len(files), model
        )
        logger.debug("[DEBUG][ITERATION_1] Target URL: %s/sessions", self.base_url)

        try:
            logger.info(f"Creating Aider session {conversation_id} " f"with {len(files)} files")

            # DEBUG LOG [ITERATION_1]: Pre-HTTP request
            logger.debug("[DEBUG][ITERATION_1] Attempting HTTP POST to %s/sessions...", self.base_url)

            response = await self.client.post(
                f"{self.base_url}/sessions",
                json={"session_id": conversation_id, "files": files, "model": model},
            )

            # DEBUG LOG [ITERATION_1]: Post-HTTP request success
            logger.debug("[DEBUG][ITERATION_1] HTTP POST successful - status_code: %s", response.status_code)

            response.raise_for_status()

            result = response.json()
            logger.info(
                "Session %s created successfully, repository_map_loaded: %s",
                conversation_id, result.get('repository_map_loaded')
            )

            return result

        except httpx.ConnectError as conn_err:
            # DEBUG LOG [ITERATION_1]: Connection-specific error (includes DNS)
            logger.error("[DEBUG][ITERATION_1] ❌ CONNECTION ERROR creating session %s", conversation_id)
            logger.error("[DEBUG][ITERATION_1] Error type: %s", type(conn_err).__name__)
            logger.error("[DEBUG][ITERATION_1] Error message: %s", str(conn_err))
            logger.error("[DEBUG][ITERATION_1] Target URL: %s/sessions", self.base_url)

            # Check if it's specifically a DNS error by examining the cause
            is_dns_error = False
            cause = conn_err.__cause__
            if cause and isinstance(cause, socket.gaierror):
                # DNS resolution error (errno -2 or -3)
                is_dns_error = True
            elif hasattr(conn_err, "args") and conn_err.args:
                # Fallback: check error message as secondary indicator
                error_msg = str(conn_err).lower()
                is_dns_error = (
                    "name resolution" in error_msg
                    or "name or service" in error_msg
                    or "nodename nor servname" in error_msg
                )

            if is_dns_error:
                logger.error("[DEBUG][ITERATION_1] 🔴 DNS RESOLUTION FAILURE CONFIRMED")
                logger.error(
                    f"[DEBUG][ITERATION_1] The hostname in '{self.base_url}' "
                    "cannot be resolved to an IP address."
                )
                logger.error("[DEBUG][ITERATION_1] Possible causes:")
                logger.error("  1. Aider-Worker service is not deployed in the cluster")
                logger.error("  2. Service name is incorrect (check spelling/namespace)")
                logger.error("  3. DNS service (CoreDNS/kube-dns) is not running")
                logger.error("  4. Network policy blocking DNS queries")
                logger.error("  5. Backend pod is not in Kubernetes cluster")

            logger.error("Failed to create session %s: %s", conversation_id, conn_err)
            raise

        except httpx.HTTPStatusError as e:
            # DEBUG LOG [ITERATION_1]: HTTP status error
            logger.error("[DEBUG][ITERATION_1] HTTP STATUS ERROR creating session %s", conversation_id)
            logger.error("[DEBUG][ITERATION_1] Status code: %s", e.response.status_code)
            logger.error("[DEBUG][ITERATION_1] Response text: %s", e.response.text)
            logger.error(
                "Failed to create session %s: %s - %s",
                conversation_id, e.response.status_code, e.response.text
            )
            raise

        except Exception as e:
            # DEBUG LOG [ITERATION_1]: Generic error
            logger.error("[DEBUG][ITERATION_1] UNEXPECTED ERROR creating session %s", conversation_id)
            logger.error("[DEBUG][ITERATION_1] Error type: %s", type(e).__name__)
            logger.error("[DEBUG][ITERATION_1] Error message: %s", str(e))
            logger.error("Error creating session %s: %s", conversation_id, e)
            raise

    async def send_command(self, session_id: str, command: str) -> AsyncIterator[str]:
        """
        Send command to active Aider session and stream output.

        Args:
            session_id: Session identifier
            command: Command to execute in Aider

        Yields:
            Lines of output from Aider (SSE stream)

        Raises:
            httpx.HTTPStatusError: If command sending fails
        """
        try:
            logger.info(f"Sending command to session {session_id}: " f"{command[:50]}...")

            async with self.client.stream(
                "POST",
                f"{self.base_url}/sessions/{session_id}/commands",
                json={"command": command},
                timeout=None,  # SSE can be long-running
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    # SSE format: "data: <content>"
                    if line.startswith("data: "):
                        yield line[6:]  # Remove "data: " prefix

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to send command to session {session_id}: " f"{e.response.status_code}"
            )
            raise

        except Exception as e:
            logger.error("Error sending command to session %s: %s", session_id, e)
            raise

    async def close_session(self, session_id: str) -> None:
        """
        Close Aider session gracefully.

        Args:
            session_id: Session identifier to close

        Raises:
            httpx.HTTPStatusError: If session closure fails
        """
        try:
            logger.info("Closing session %s", session_id)

            response = await self.client.delete(f"{self.base_url}/sessions/{session_id}")
            response.raise_for_status()

            logger.info("Session %s closed successfully", session_id)

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to close session {session_id}: " f"{e.response.status_code}")
            raise

        except Exception as e:
            logger.error("Error closing session %s: %s", session_id, e)
            raise

    async def health_check(self) -> dict:
        """
        Check health of Aider-Worker service.

        Returns:
            Health check response with status and active_sessions count

        Raises:
            httpx.HTTPStatusError: If health check fails
        """
        try:
            response = await self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("Health check failed: %s", e.response.status_code)
            raise

        except Exception as e:
            logger.error("Error during health check: %s", e)
            raise

    async def list_sessions(self) -> dict:
        """
        List all active sessions in Aider-Worker.

        Returns:
            Dictionary with active_sessions list and count

        Raises:
            httpx.HTTPStatusError: If listing fails
        """
        try:
            response = await self.client.get(f"{self.base_url}/sessions")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("Failed to list sessions: %s", e.response.status_code)
            raise

        except Exception as e:
            logger.error("Error listing sessions: %s", e)
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("AiderWorkerClient closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
