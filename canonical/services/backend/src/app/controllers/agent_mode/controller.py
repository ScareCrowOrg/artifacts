"""
Agent Mode Controller - Orchestrates Aider-Worker integration.

This controller manages the lifecycle of Agent Mode sessions,
relaying commands and streaming responses between the frontend
and the Aider-Worker microservice.

MVP 3 Implementation: Backend Core bridge to Aider-Worker.
MVP 4 Enhancement: Redis pub/sub for real-time telemetry.
"""

import logging
import json
from typing import AsyncIterator, Dict, List, Optional
from datetime import datetime

from app.services.aider.aider_client import AiderWorkerClient
from app.services.redis_pubsub_service import get_pubsub_service

logger = logging.getLogger(__name__)


class AgentModeController:
    """
    Controller for Agent Mode operations.

    Responsibilities:
    - Create and manage Aider sessions via AiderWorkerClient
    - Relay commands to Aider-Worker with SSE streaming
    - Handle session lifecycle (create, process, close)
    - Maintain session state tracking
    """

    def __init__(self, aider_client: Optional[AiderWorkerClient] = None):
        """
        Initialize AgentModeController.

        Args:
            aider_client: Optional AiderWorkerClient instance.
                         If None, creates a new client.
        """
        self.aider_client = aider_client or AiderWorkerClient()
        self.active_sessions: Dict[str, dict] = {}
        self._pubsub_service = None  # Will be initialized async
        logger.info("AgentModeController initialized")

    async def _get_pubsub_service(self):
        """
        Get Redis pub/sub service instance (lazy initialization).

        Returns:
            RedisPubSubService instance or None if unavailable
        """
        if self._pubsub_service is None:
            try:
                self._pubsub_service = await get_pubsub_service()
            except Exception as e:
                logger.warning("Redis pub/sub not available: %s", e)
                return None
        return self._pubsub_service

    async def _publish_log(self, conversation_id: str, message: dict) -> None:
        """
        Publish log message to Redis channel for WebSocket streaming.

        Channel format: agent:logs:{conversation_id}

        MVP 4.1: Implements actual Redis publishing for real-time telemetry.
        WebSocket clients subscribe to this channel to receive live logs.

        Args:
            conversation_id: Session identifier
            message: Log message dict to publish
        """
        try:
            pubsub = await self._get_pubsub_service()
            if pubsub is None:
                logger.debug("Redis pub/sub not available, skipping log publish for %s", conversation_id)
                return

            # MVP 4.1: Actual Redis publishing implementation
            channel = f"agent:logs:{conversation_id}"

            # Publish message to Redis channel
            await pubsub._redis_client.publish(channel, json.dumps(message))

            logger.debug("Published log to Redis channel: %s, type: %s", channel, message.get('type', 'unknown'))

        except Exception as e:
            logger.warning("Failed to publish log to Redis: %s", e)
            # Don't fail the command processing if Redis is unavailable

    async def create_session(
        self, conversation_id: str, files: List[str], model: str = "ollama/qwen2.5-coder:14b"
    ) -> dict:
        """
        Create new Aider session in the worker.

        Args:
            conversation_id: Unique conversation identifier
            files: List of file paths to include in context
            model: LLM model to use for code generation

        Returns:
            Session creation response with status

        Raises:
            Exception: If session creation fails
        """
        # DEBUG LOG [ITERATION_1]: Pre-session creation
        logger.debug("[DEBUG][ITERATION_1] AgentModeController.create_session called - conversation_id: %s, files: %s, model: %s", conversation_id, files, model)
        logger.debug("[DEBUG][ITERATION_1] Active sessions before creation: %s", list(self.active_sessions.keys()))

        try:
            logger.info("Creating Agent Mode session for conversation: %s", conversation_id)

            # DEBUG LOG [ITERATION_1]: Before client call
            logger.debug("[DEBUG][ITERATION_1] Calling aider_client.create_session...")
            logger.debug("[DEBUG][ITERATION_1] Client base_url: %s", self.aider_client.base_url)

            # Create session in Aider-Worker
            response = await self.aider_client.create_session(
                conversation_id=conversation_id, files=files, model=model
            )

            # DEBUG LOG [ITERATION_1]: After successful client call
            logger.debug("[DEBUG][ITERATION_1] aider_client.create_session returned successfully")
            logger.debug("[DEBUG][ITERATION_1] Response: %s", response)

            # Track session locally
            self.active_sessions[conversation_id] = {
                "conversation_id": conversation_id,
                "files": files,
                "model": model,
                "created_at": datetime.utcnow().isoformat(),
                "status": "active",
            }

            logger.info(
                "Agent Mode session %s created successfully. Repository Map loaded: %s",
                conversation_id, response.get('repository_map_loaded')
            )

            # DEBUG LOG [ITERATION_1]: Final state
            logger.debug("[DEBUG][ITERATION_1] Session %s added to active_sessions", conversation_id)
            logger.debug("[DEBUG][ITERATION_1] Active sessions after creation: %s", list(self.active_sessions.keys()))

            return {
                "session_id": conversation_id,
                "status": "created",
                "repository_map_loaded": response.get("repository_map_loaded"),
                "files_count": len(files),
                "model": model,
            }

        except Exception as e:
            # DEBUG LOG [ITERATION_1]: Error details
            logger.error("[DEBUG][ITERATION_1] ❌ EXCEPTION in AgentModeController.create_session")
            logger.error("[DEBUG][ITERATION_1] Exception type: %s", type(e).__name__)
            logger.error("[DEBUG][ITERATION_1] Exception message: %s", str(e))
            logger.error("[DEBUG][ITERATION_1] Conversation ID: %s", conversation_id)

            logger.error("Failed to create Agent Mode session %s: %s", conversation_id, e)
            # Update session status
            if conversation_id in self.active_sessions:
                self.active_sessions[conversation_id]["status"] = "error"
                logger.debug("[DEBUG][ITERATION_1] Updated session %s status to 'error'", conversation_id)
            raise

    async def process_command(self, conversation_id: str, command: str) -> AsyncIterator[dict]:
        """
        Process command in Agent Mode session with streaming.

        This method relays the command to Aider-Worker and streams
        the output back to the frontend in real-time.

        Args:
            conversation_id: Session identifier
            command: User command to execute

        Yields:
            Streaming messages with type and content

        Raises:
            ValueError: If session not found
            Exception: If command processing fails
        """
        # Validate session exists
        if conversation_id not in self.active_sessions:
            error_msg = f"Session {conversation_id} not found"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            logger.info("Processing Agent Mode command for session %s: %s...", conversation_id, command[:50])

            # Stream command output from Aider-Worker
            async for line in self.aider_client.send_command(
                session_id=conversation_id, command=command
            ):
                # Create log message
                log_message = {
                    "type": "log",
                    "content": line,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                # MVP 4.1: Publish to Redis for WebSocket streaming
                await self._publish_log(conversation_id, log_message)

                # Also yield for SSE streaming (backwards compatible)
                yield log_message

            # Send completion message
            completion_message = {
                "type": "status",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

            # MVP 4.1: Publish completion to Redis
            await self._publish_log(conversation_id, completion_message)

            yield completion_message

            logger.info("Agent Mode command completed for session %s", conversation_id)

        except Exception as e:
            error_msg = f"Error processing command in session {conversation_id}: {e}"
            logger.error(error_msg)

            # Create error message
            error_message = {
                "type": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

            # MVP 4.1: Publish error to Redis
            await self._publish_log(conversation_id, error_message)

            # Send error message via SSE
            yield error_message

            # Update session status
            self.active_sessions[conversation_id]["status"] = "error"

    async def close_session(self, conversation_id: str) -> dict:
        """
        Close Agent Mode session gracefully.

        Args:
            conversation_id: Session identifier to close

        Returns:
            Closure confirmation

        Raises:
            ValueError: If session not found
        """
        if conversation_id not in self.active_sessions:
            error_msg = f"Session {conversation_id} not found"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            logger.info("Closing Agent Mode session: %s", conversation_id)

            # Close session in Aider-Worker
            await self.aider_client.close_session(conversation_id)

            # Remove from active sessions
            session_info = self.active_sessions.pop(conversation_id)

            logger.info("Agent Mode session %s closed successfully", conversation_id)

            return {
                "session_id": conversation_id,
                "status": "closed",
                "closed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error("Failed to close session %s: %s", conversation_id, e)
            raise

    async def get_session_status(self, conversation_id: str) -> dict:
        """
        Get status of Agent Mode session.

        Args:
            conversation_id: Session identifier

        Returns:
            Session status information

        Raises:
            ValueError: If session not found
        """
        if conversation_id not in self.active_sessions:
            raise ValueError(f"Session {conversation_id} not found")

        return self.active_sessions[conversation_id]

    async def list_active_sessions(self) -> List[dict]:
        """
        List all active Agent Mode sessions.

        Returns:
            List of active session information
        """
        return list(self.active_sessions.values())

    async def health_check(self) -> dict:
        """
        Check health of Aider-Worker service.

        Returns:
            Health status from Aider-Worker
        """
        try:
            return await self.aider_client.health_check()
        except Exception as e:
            logger.error("Aider-Worker health check failed: %s", e)
            return {"status": "unhealthy", "error": str(e)}

    async def cleanup(self):
        """
        Cleanup controller resources.

        Closes all active sessions and the HTTP client.
        """
        logger.info("Cleaning up AgentModeController...")

        # Close all active sessions
        for conversation_id in list(self.active_sessions.keys()):
            try:
                await self.close_session(conversation_id)
            except Exception as e:
                logger.error("Error closing session %s during cleanup: %s", conversation_id, e)

        # Close HTTP client
        await self.aider_client.close()

        logger.info("AgentModeController cleanup complete")
