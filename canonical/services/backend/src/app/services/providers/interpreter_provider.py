"""
Interpreter Provider Implementation

Concrete implementation of BaseLLMProvider for Open Interpreter integration
via the aider-worker service. Provides stateless execution with history injection
for exploration and planning capabilities.
"""

import logging
import httpx
from typing import List, Dict, Any, Optional

from ..llm_provider_interface import BaseLLMProvider, LLMProviderError
from ...config import AIDER_WORKER_BASE_URL, AIDER_WORKER_TIMEOUT

logger = logging.getLogger(__name__)


class InterpreterProvider(BaseLLMProvider):
    """
    Open Interpreter LLM Provider implementation.

    This provider integrates with the aider-worker service to provide
    Open Interpreter capabilities through the ScareVerse chat interface.
    It communicates with the ephemeral execution endpoint to run interpreter
    commands with stateless history injection.

    Features:
    - Stateless operation (history injected per request)
    - Session-aware execution (uses session_id for workspace targeting)
    - Returns structured responses (analysis + plan)
    - Graceful error handling for service unavailability

    Args:
        base_url: Base URL of aider-worker service (default: from config)
        timeout: Request timeout in seconds (default: from config)

    Example:
        >>> provider = InterpreterProvider()
        >>> result = await provider.process_chat(
        ...     user_message="Analyze the project structure",
        ...     conversation_history=[...],
        ...     session_id="chat_123"
        ... )
        >>> print(result["response"])  # Contains analysis + plan
    """

    # Response formatting constants
    FORMAT_ANALYSIS = "**Analysis:**\n{}"
    FORMAT_PLAN = "\n**Action Plan:**\n{}"
    """
    Open Interpreter LLM Provider implementation.

    This provider integrates with the aider-worker service to provide
    Open Interpreter capabilities through the ScareVerse chat interface.
    It communicates with the ephemeral execution endpoint to run interpreter
    commands with stateless history injection.

    Features:
    - Stateless operation (history injected per request)
    - Session-aware execution (uses session_id for workspace targeting)
    - Returns structured responses (analysis + plan)
    - Graceful error handling for service unavailability

    Args:
        base_url: Base URL of aider-worker service (default: from config)
        timeout: Request timeout in seconds (default: from config)

    Example:
        >>> provider = InterpreterProvider()
        >>> result = await provider.process_chat(
        ...     user_message="Analyze the project structure",
        ...     conversation_history=[...],
        ...     session_id="chat_123"
        ... )
        >>> print(result["response"])  # Contains analysis + plan
    """

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        """Initialize Interpreter provider with configuration."""
        self._base_url = (base_url or AIDER_WORKER_BASE_URL).rstrip("/")
        self._timeout = timeout or AIDER_WORKER_TIMEOUT

        logger.debug(
            f"InterpreterProvider initialized - "
            f"base_url: {self._base_url}, "
            f"timeout: {self._timeout}s"
        )

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "scare-worker"

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return "open-interpreter"

    async def verify_availability(self) -> bool:
        """
        Check if aider-worker service is available.

        Returns:
            True if service is reachable, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                health_url = f"{self._base_url}/sessions/ephemeral/health"
                response = await client.get(health_url)

                if response.status_code == 200:
                    data = response.json()
                    is_healthy = data.get("status") == "healthy"
                    logger.info(
                        f"Aider-worker health check: {data.get('status')} "
                        f"(orchestrator_initialized: {data.get('orchestrator_initialized')})"
                    )
                    return is_healthy
                else:
                    logger.warning("Aider-worker health check failed: %s", response.status_code)
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
        custom_instructions: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Process chat with Open Interpreter via aider-worker.

        This method sends a request to the aider-worker's /interpret endpoint
        with the user message and conversation history. The worker executes
        Open Interpreter in a stateless manner, injecting history per request.

        Args:
            user_message: Current user message/intent
            conversation_history: Previous conversation turns (optional)
            rag_context: RAG context (ignored by interpreter)
            attached_content_metadata: Attached content (ignored by interpreter)
            system_instructions: System-level instructions (optional)
            use_rag: Whether to use RAG (ignored by interpreter)
            selected_collections: RAG collections (ignored by interpreter)
            session_id: Session identifier for workspace targeting (optional, will be built from conversation_id)
            conversation_id: Conversation identifier for building session_id (optional)
            custom_instructions: Custom instructions for Open Interpreter behavior (optional)
            **kwargs: Additional parameters

        Returns:
            Dict containing:
                - response: str - Combined analysis and plan from interpreter
                - raw_output: str - Full interpreter output (optional)

        Raises:
            LLMProviderError: If aider-worker is unavailable or request fails
        """
        conversation_history = conversation_history or []

        # Build session_id from conversation_id if provided
        # Priority: explicit session_id > conversation_id > "default-session"
        if not session_id:
            conversation_id = conversation_id or kwargs.get("conversation_id")

            logger.debug(
                f"[CONV_ID] InterpreterProvider - Building session_id: "
                f"conversation_id from param={conversation_id}, "
                f"conversation_id from kwargs={kwargs.get('conversation_id', 'NOT_IN_KWARGS')}"
            )

            if conversation_id:
                session_id = f"conversation-{conversation_id}"
                logger.info(
                    f"[CONV_ID] InterpreterProvider - ✓ session_id built from conversation_id: "
                    f"conversation_id={conversation_id}, session_id={session_id}"
                )
            else:
                session_id = "default-session"
                logger.warning(
                    f"[CONV_ID] InterpreterProvider - ✗ No conversation_id provided, using fallback: "
                    f"session_id={session_id} (ALL CONVERSATIONS WILL SHARE THIS SESSION)"
                )

        logger.info(
            f"InterpreterProvider processing chat - "
            f"Session: {session_id}, "
            f"Message length: {len(user_message)}, "
            f"History: {len(conversation_history)} msgs, "
            f"conversation_id: {conversation_id or kwargs.get('conversation_id', 'None')}"
        )

        # Build the interpret request
        # Convert conversation history to the format expected by aider-worker
        history_entries = []
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Filter out system messages and empty content
            if content and role in ["user", "assistant"]:
                history_entries.append({"role": role, "content": content})

        # Prepare request payload
        request_payload = {"prompt": user_message}

        # Only include history if there are entries
        if history_entries:
            request_payload["history"] = history_entries

        # Add custom instructions if provided
        # Custom instructions take precedence over system instructions
        instructions_to_use = custom_instructions or system_instructions
        if instructions_to_use:
            # Pass custom_instructions as a separate field to aider-worker
            # Also prepend to prompt for backward compatibility
            request_payload["custom_instructions"] = instructions_to_use
            request_payload["prompt"] = (
                f"System Instructions: {instructions_to_use}\n\n" f"User Request: {user_message}"
            )

        logger.debug(
            f"Sending interpret request - "
            f"Session: {session_id}, "
            f"Payload: {len(str(request_payload))} bytes, "
            f"History entries: {len(history_entries)}"
        )

        # Call aider-worker /interpret endpoint
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                interpret_url = f"{self._base_url}/sessions/ephemeral/{session_id}/interpret"

                response = await client.post(interpret_url, json=request_payload)

                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(
                        f"Aider-worker returned error {response.status_code}: " f"{error_detail}"
                    )
                    raise LLMProviderError(
                        f"Aider-worker request failed (HTTP {response.status_code}): "
                        f"{error_detail}",
                        provider=self.provider_name,
                    )

                result = response.json()

                # Extract response components
                analysis = result.get("analysis", "")
                plan = result.get("plan", "")
                raw_output = result.get("output", "")
                status = result.get("status", "unknown")

                logger.info(
                    f"Interpreter response received - "
                    f"Status: {status}, "
                    f"Analysis: {len(analysis) if analysis else 0} chars, "
                    f"Plan: {len(plan) if plan else 0} chars, "
                    f"Raw output: {len(raw_output)} chars"
                )

                # Combine analysis and plan into response
                response_parts = []

                if analysis:
                    response_parts.append(self.FORMAT_ANALYSIS.format(analysis))

                if plan:
                    response_parts.append(self.FORMAT_PLAN.format(plan))

                # If neither analysis nor plan, use raw output
                if not response_parts:
                    if raw_output:
                        response_text = raw_output
                    else:
                        response_text = (
                            "Interpreter execution completed, but no "
                            "analysis or plan was generated."
                        )
                else:
                    response_text = "\n".join(response_parts)

                return {"response": response_text, "raw_output": raw_output, "status": status}

        except httpx.TimeoutException as e:
            logger.error("Aider-worker request timeout: %s", e)
            raise LLMProviderError(
                f"Aider-worker request timed out after {self._timeout}s. "
                "The service may be busy or unresponsive.",
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
            logger.error("Unexpected error processing interpreter request: %s", e, exc_info=True)
            raise LLMProviderError(
                f"Failed to process interpreter request: {str(e)}", provider=self.provider_name
            ) from e
