"""
Repository Access Worker for Event Bus.

Listens to file access requests from the event bus and serves
file contents from the repository.
"""

import logging
from pathlib import Path
from typing import Optional

from ..config import BASE_DIR
from ..models.event_bus import (
    ErrorResponse,
    EventTopic,
    FileAccessRequest,
    FileAccessResponse,
    MessageEnvelope,
)
from ..services.redis_pubsub_service import get_pubsub_service

logger = logging.getLogger(__name__)


class RepositoryAccessWorker:
    """
    Worker that processes file access requests from the event bus.

    Features:
    - Listen to agent:request:file_access channel
    - Read files from repository (BASE_DIR)
    - Validate file paths (prevent directory traversal)
    - Publish file contents to agent:response:file_data
    - Handle errors gracefully
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the repository access worker.

        Args:
            base_dir: Base directory for file access (defaults to BASE_DIR from config)
        """
        self.base_dir = base_dir or BASE_DIR
        self._is_running = False
        self._pubsub_service = None

        logger.info("Repository access worker initialized with BASE_DIR: %s", self.base_dir)

    async def start(self):
        """
        Start the worker and subscribe to file access requests.
        """
        if self._is_running:
            logger.warning("Worker already running")
            return

        self._pubsub_service = await get_pubsub_service()

        # Subscribe to file access requests
        await self._pubsub_service.subscribe(
            EventTopic.AGENT_REQUEST_FILE_ACCESS.value, self._handle_file_access_request
        )

        self._is_running = True
        logger.info("Repository access worker started")

    async def stop(self):
        """
        Stop the worker and unsubscribe from channels.
        """
        if not self._is_running:
            return

        if self._pubsub_service:
            await self._pubsub_service.unsubscribe(
                EventTopic.AGENT_REQUEST_FILE_ACCESS.value,
                self._handle_file_access_request,
            )

        self._is_running = False
        logger.info("Repository access worker stopped")

    async def _handle_file_access_request(self, message: MessageEnvelope):
        """
        Handle a file access request message.

        Args:
            message: Message envelope containing FileAccessRequest payload
        """
        try:
            # Parse request
            request = FileAccessRequest(**message.payload)

            logger.info("Processing file access request: %s", request.path)

            # Resolve and validate file path
            file_path = self._resolve_path(request.path)

            if file_path is None:
                await self._send_error_response(
                    message,
                    "INVALID_PATH",
                    f"Invalid or unsafe file path: {request.path}",
                )
                return

            # Check if file exists
            if not file_path.exists():
                await self._send_error_response(
                    message, "FILE_NOT_FOUND", f"File not found: {request.path}"
                )
                return

            # Check if it's a file (not a directory)
            if not file_path.is_file():
                await self._send_error_response(
                    message, "NOT_A_FILE", f"Path is not a file: {request.path}"
                )
                return

            # Read file content
            try:
                content = file_path.read_text(encoding=request.encoding)
                file_size = file_path.stat().st_size

                # Send success response
                await self._send_file_response(
                    message, request.path, content, file_size, request.encoding
                )

                logger.info("File access successful: %s (%s bytes)", request.path, file_size)

            except UnicodeDecodeError as e:
                await self._send_error_response(
                    message,
                    "ENCODING_ERROR",
                    f"Failed to decode file with encoding '{request.encoding}': {str(e)}",
                )
            except PermissionError as e:
                await self._send_error_response(
                    message,
                    "PERMISSION_DENIED",
                    f"Permission denied reading file: {str(e)}",
                )

        except Exception as e:
            logger.error("Error handling file access request: %s", e, exc_info=True)
            await self._send_error_response(
                message,
                "INTERNAL_ERROR",
                f"Internal error processing file access: {str(e)}",
            )

    def _resolve_path(self, requested_path: str) -> Optional[Path]:
        """
        Resolve and validate a file path.

        Ensures the path is within BASE_DIR (prevents directory traversal attacks).

        Args:
            requested_path: Relative path requested by client

        Returns:
            Resolved Path object or None if invalid/unsafe
        """
        try:
            # Remove leading slashes
            clean_path = requested_path.lstrip("/")

            # Resolve full path
            full_path = (self.base_dir / clean_path).resolve()

            # Verify it's within BASE_DIR (security check)
            if not str(full_path).startswith(str(self.base_dir.resolve())):
                logger.warning("Path traversal attempt blocked: %s", requested_path)
                return None

            return full_path

        except Exception as e:
            logger.error("Error resolving path '%s': %s", requested_path, e)
            return None

    async def _send_file_response(
        self,
        original_message: MessageEnvelope,
        path: str,
        content: str,
        size: int,
        encoding: str,
    ):
        """
        Send a successful file access response.

        Args:
            original_message: Original request message
            path: File path
            content: File content
            size: File size in bytes
            encoding: Encoding used
        """
        response = FileAccessResponse(
            path=path, content=content, size=size, encoding=encoding
        )

        response_message = MessageEnvelope(
            source="backend-repository-worker",
            topic=EventTopic.AGENT_RESPONSE_FILE_DATA.value,
            payload=response.model_dump(),
            correlation_id=original_message.trace_id,
        )

        if self._pubsub_service:
            await self._pubsub_service.publish(response_message)

    async def _send_error_response(
        self, original_message: MessageEnvelope, error_code: str, error_message: str
    ):
        """
        Send an error response.

        Args:
            original_message: Original request message
            error_code: Error code identifier
            error_message: Human-readable error message
        """
        error = ErrorResponse(error_code=error_code, message=error_message)

        error_message_envelope = MessageEnvelope(
            source="backend-repository-worker",
            topic=EventTopic.AGENT_RESPONSE_ERROR.value,
            payload=error.model_dump(),
            correlation_id=original_message.trace_id,
        )

        if self._pubsub_service:
            await self._pubsub_service.publish(error_message_envelope)


# Global worker instance
_worker: Optional[RepositoryAccessWorker] = None


async def start_repository_worker():
    """
    Start the global repository access worker.

    Returns:
        The worker instance
    """
    global _worker

    if _worker is None:
        _worker = RepositoryAccessWorker()

    await _worker.start()
    return _worker


async def stop_repository_worker():
    """Stop the global repository access worker."""
    global _worker

    if _worker is not None:
        await _worker.stop()
        _worker = None
