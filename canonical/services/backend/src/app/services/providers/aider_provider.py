"""
Aider Provider Implementation

Concrete implementation of BaseLLMProvider for Aider code execution integration
via the aider-worker service. Provides code modification capabilities through
atomic execution with session-based git tracking.
"""

import logging
import httpx
from typing import List, Dict, Any, Optional

from ..llm_provider_interface import BaseLLMProvider, LLMProviderError
from ...config import AIDER_WORKER_BASE_URL, AIDER_WORKER_TIMEOUT

logger = logging.getLogger(__name__)


class AiderProvider(BaseLLMProvider):
    """
    Aider LLM Provider implementation.

    This provider integrates with the aider-worker service to provide
    Aider code execution capabilities through the ScareVerse chat interface.
    It communicates with the ephemeral execution endpoint to run aider commands
    with file context and git-based change tracking.

    Features:
    - Session-aware execution (uses session_id for workspace targeting)
    - File context support (specify files for Aider to modify)
    - Git-based change tracking (session persists modifications)
    - Atomic execution (complete output returned per request)
    - Graceful error handling for service unavailability

    Args:
        base_url: Base URL of aider-worker service (default: from config)
        timeout: Request timeout in seconds (default: from config)

    Example:
        >>> provider = AiderProvider()
        >>> result = await provider.process_chat(
        ...     user_message="Add type hints to the function",
        ...     files=["app/utils.py"],
        ...     session_id="chat_123"
        ... )
        >>> print(result["response"])  # Contains execution output
    """

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        """Initialize Aider provider with configuration."""
        self._base_url = (base_url or AIDER_WORKER_BASE_URL).rstrip("/")
        self._timeout = timeout or AIDER_WORKER_TIMEOUT

        # Ensure timeout is within acceptable range
        if self._timeout < 10:
            logger.warning("Aider timeout %ss is too low, setting to 10s minimum", self._timeout)
            self._timeout = 10
        elif self._timeout > 1800:
            logger.warning("Aider timeout %ss is too high, capping to 1800s maximum", self._timeout)
            self._timeout = 1800

        logger.info(
            f"AiderProvider initialized - "
            f"base_url: {self._base_url}, "
            f"timeout: {self._timeout}s"
        )

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "scare-aider"

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return "aider-coder"

    async def verify_availability(self) -> bool:
        """
        Check if aider-worker service is available.

        Returns:
            True if service is reachable and healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                health_url = f"{self._base_url}/sessions/ephemeral/health"
                response = await client.get(health_url)

                if response.status_code == 200:
                    data = response.json()
                    is_healthy = data.get("status") == "healthy"
                    logger.info(
                        f"Aider health check: {data.get('status')} "
                        f"(orchestrator_initialized: {data.get('orchestrator_initialized')})"
                    )
                    return is_healthy
                else:
                    logger.warning("Aider health check failed: %s", response.status_code)
                    return False

        except Exception as e:
            logger.error("Error checking aider-worker availability: %s", e)
            return False

    async def process_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        rag_context: Optional[str] = None,
        attached_content_metadata: Optional[List[Dict[str, Any]]] = None,
        system_instructions: Optional[str] = None,
        use_rag: bool = True,
        selected_collections: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        files: Optional[List[str]] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        additional_args: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Process chat with Aider via aider-worker.

        This method sends a request to the aider-worker's /execute endpoint
        with the user message and optional file context. The worker executes
        Aider command and returns the complete output atomically.

        Args:
            user_message: Current user message/intent (the prompt for Aider)
            conversation_history: Previous conversation turns (ignored by Aider)
            rag_context: RAG context (ignored by Aider)
            attached_content_metadata: Attached content (ignored by Aider)
            system_instructions: System-level instructions (ignored by Aider)
            use_rag: Whether to use RAG (ignored by Aider)
            selected_collections: RAG collections (ignored by Aider)
            session_id: Session identifier for workspace targeting (optional, will be built from conversation_id)
            conversation_id: Conversation identifier for building session_id (optional)
            files: List of file paths for Aider to consider (optional)
            model: Model override for Aider execution (optional)
            timeout: Timeout override for this request (optional)
            additional_args: Additional CLI arguments for Aider (optional)
            **kwargs: Additional parameters

        Returns:
            Dict containing:
                - response: str - Aider execution output
                - status: str - Execution status (always "success" if no exception)
                - metrics: dict - Optional execution metrics

        Raises:
            LLMProviderError: If aider-worker is unavailable or request fails
        """
        # Validate user_message
        if not user_message or not isinstance(user_message, str):
            raise LLMProviderError(
                "user_message must be a non-empty string", provider=self.provider_name
            )

        # Build session_id from conversation_id if provided
        # Priority: explicit session_id > conversation_id > "default-session"
        if not session_id:
            conversation_id = conversation_id or kwargs.get("conversation_id")

            logger.debug(
                f"[CONV_ID] AiderProvider - Building session_id: "
                f"conversation_id from param={conversation_id}"
            )

            if conversation_id:
                session_id = f"conversation-{conversation_id}"
                logger.info(
                    f"[CONV_ID] AiderProvider - ✓ session_id built from conversation_id: "
                    f"conversation_id={conversation_id}, session_id={session_id}"
                )
            else:
                session_id = "default-session"
                logger.warning(
                    f"[CONV_ID] AiderProvider - ✗ No conversation_id provided, using fallback: "
                    f"session_id={session_id} (ALL CONVERSATIONS WILL SHARE THIS SESSION)"
                )

        logger.info(
            f"AiderProvider processing chat - "
            f"Session: {session_id}, "
            f"Message length: {len(user_message)}, "
            f"Files: {len(files) if files else 0}"
        )

        # Build the execute request
        request_payload = {
            "prompt": user_message,
        }

        # Add optional fields only if provided
        if files:
            request_payload["files"] = files
            logger.debug("Including %s files in request: %s", len(files), files)

        if model:
            request_payload["model"] = model
            logger.debug("Using custom model: %s", model)

        # Use timeout parameter or instance default
        request_timeout = timeout or self._timeout
        # Ensure timeout is within acceptable range
        if request_timeout < 10:
            logger.warning("Request timeout %ss is too low, setting to 10s minimum", request_timeout)
            request_timeout = 10
        elif request_timeout > 1800:
            logger.warning("Request timeout %ss is too high, capping to 1800s maximum", request_timeout)
            request_timeout = 1800

        request_payload["timeout"] = request_timeout

        if additional_args:
            request_payload["additional_args"] = additional_args
            logger.debug("Including additional args: %s", additional_args)

        logger.debug(
            f"Sending execute request - "
            f"Session: {session_id}, "
            f"Payload: {len(str(request_payload))} bytes"
        )

        # Call aider-worker /execute endpoint
        try:
            async with httpx.AsyncClient(timeout=request_timeout + 10) as client:
                execute_url = f"{self._base_url}/sessions/ephemeral/{session_id}/execute"

                response = await client.post(execute_url, json=request_payload)

                # Handle different HTTP error codes
                if response.status_code == 400:
                    error_detail = response.text
                    logger.error("Aider-worker returned HTTP 400 (Invalid request): %s", error_detail)
                    raise LLMProviderError(
                        f"Invalid request: {error_detail}", provider=self.provider_name
                    )
                elif response.status_code == 503:
                    error_detail = response.text
                    logger.error("Aider-worker returned HTTP 503 (Service unavailable): %s", error_detail)
                    raise LLMProviderError(
                        f"Service unavailable (orchestrator not initialized): {error_detail}",
                        provider=self.provider_name,
                    )
                elif response.status_code == 504:
                    error_detail = response.text
                    logger.error("Aider-worker returned HTTP 504 (Timeout): %s", error_detail)
                    raise LLMProviderError(
                        f"Execution timeout: {error_detail}", provider=self.provider_name
                    )
                elif response.status_code == 500:
                    error_detail = response.text
                    logger.error("Aider-worker returned HTTP 500 (Execution failed): %s", error_detail)
                    raise LLMProviderError(
                        f"Execution failed: {error_detail}", provider=self.provider_name
                    )
                elif response.status_code != 200:
                    error_detail = response.text
                    logger.error("Aider-worker returned error %s: %s", response.status_code, error_detail)
                    raise LLMProviderError(
                        f"Aider-worker request failed (HTTP {response.status_code}): {error_detail}",
                        provider=self.provider_name,
                    )

                result = response.json()

                # Extract response components
                output = result.get("output", "")
                status = result.get("status", "success")
                metrics = result.get("metrics", {})

                logger.info(
                    f"Aider execution response received - "
                    f"Status: {status}, "
                    f"Output: {len(output)} chars"
                )

                # Return standardized response
                response_dict = {"response": output, "status": status}

                # Include metrics if available
                if metrics:
                    response_dict["metrics"] = metrics

                return response_dict

        except httpx.TimeoutException as e:
            logger.error("Aider-worker request timeout: %s", e)
            raise LLMProviderError(
                f"Aider execution timed out after {request_timeout}s. "
                "The service may be busy or the task may require more time.",
                provider=self.provider_name,
            ) from e

        except httpx.ConnectError as e:
            logger.error("Cannot connect to aider-worker: %s", e)
            raise LLMProviderError(
                f"Cannot connect to aider-worker at {self._base_url}. "
                "Please ensure the service is running and accessible.",
                provider=self.provider_name,
            ) from e

        except httpx.HTTPError as e:
            logger.error("HTTP error during aider-worker request: %s", e)
            raise LLMProviderError(
                f"HTTP error communicating with aider-worker: {str(e)}", provider=self.provider_name
            ) from e

        except Exception as e:
            logger.error("Unexpected error processing aider request: %s", e, exc_info=True)
            raise LLMProviderError(
                f"Failed to process aider request: {str(e)}", provider=self.provider_name
            ) from e
