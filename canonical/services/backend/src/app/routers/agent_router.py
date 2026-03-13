"""
Agent Mode API Router - MVP 3 Implementation.

Provides RESTful endpoints for Agent Mode session management
and command processing with real-time streaming.

Endpoints:
- POST /agent/sessions - Create new Agent Mode session
- POST /agent/chat - Process command with streaming
- DELETE /agent/sessions/{conversation_id} - Close session
- GET /agent/sessions/{conversation_id} - Get session status
- GET /agent/sessions - List all active sessions
- GET /agent/health - Health check of Aider-Worker
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth_legacy import get_current_user
from app.controllers.agent_mode import AgentModeController
from app.models.users import User

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["agent-mode"])

# Global controller instance (initialized on startup)
_agent_controller: AgentModeController = None


def get_agent_controller() -> AgentModeController:
    """
    Dependency to get AgentModeController instance.

    Returns:
        AgentModeController instance

    Raises:
        HTTPException: If controller not initialized
    """
    global _agent_controller
    if _agent_controller is None:
        _agent_controller = AgentModeController()
    return _agent_controller


# Request/Response Models


class CreateSessionRequest(BaseModel):
    """Request model for creating Agent Mode session."""

    conversation_id: str = Field(..., description="Unique conversation identifier")
    files: List[str] = Field(
        default=[], description="List of file paths to include in Aider context"
    )
    model: str = Field(
        default="ollama/qwen2.5-coder:14b", description="LLM model to use"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_123456",
                "files": ["src/main.py", "src/utils.py"],
                "model": "ollama/qwen2.5-coder:14b",
            }
        }


class ChatRequest(BaseModel):
    """Request model for Agent Mode chat."""

    conversation_id: str = Field(..., description="Session identifier")
    command: str = Field(..., description="User command to execute")

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_123456",
                "command": "Add docstrings to all functions in main.py",
            }
        }


class SessionResponse(BaseModel):
    """Response model for session operations."""

    session_id: str
    status: str

    class Config:
        json_schema_extra = {
            "example": {"session_id": "conv_123456", "status": "created"}
        }


# API Endpoints


@router.post("/agent/sessions", response_model=dict)
async def create_session(
    request: CreateSessionRequest,
    controller: AgentModeController = Depends(get_agent_controller),
    current_user: User = Depends(get_current_user),
):
    """
    Create new Agent Mode session.

    Initializes an Aider session in the worker with the specified files.
    The session will load the Repository Map, which may take 60-90 seconds
    for large projects.

    Args:
        request: Session creation parameters
        controller: AgentModeController instance
        current_user: Authenticated user

    Returns:
        Session creation response with status

    Raises:
        HTTPException: If session creation fails
    """
    # DEBUG LOG [ITERATION_1]: Request received
    logger.debug("[DEBUG][ITERATION_1] POST /api/agent/sessions received")
    logger.debug(
        "[DEBUG][ITERATION_1] Request data - conversation_id: %s, files: %s, model: %s",
        request.conversation_id, request.files, request.model
    )

    try:
        # Debug logging: log user attributes
        logger.debug(
            "Creating Agent Mode session for user - ID: %s, Email: %s, Name: %s",
            current_user.id, current_user.email, current_user.name
        )

        logger.info(
            "User %s (ID: %s) creating Agent Mode session: %s",
            current_user.email, current_user.id, request.conversation_id
        )

        # DEBUG LOG [ITERATION_1]: Before controller call
        logger.debug("[DEBUG][ITERATION_1] Calling controller.create_session...")

        response = await controller.create_session(
            conversation_id=request.conversation_id,
            files=request.files,
            model=request.model,
        )

        # DEBUG LOG [ITERATION_1]: Success
        logger.debug(
            "[DEBUG][ITERATION_1] controller.create_session completed successfully"
        )
        logger.debug("[DEBUG][ITERATION_1] Response: %s", response)

        return response

    except AttributeError as e:
        # DEBUG LOG [ITERATION_1]: Attribute error
        logger.error("[DEBUG][ITERATION_1] AttributeError in create_session endpoint")
        logger.error("User attribute error during session creation: %s", e)
        logger.debug("User object attributes: %s", dir(current_user))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create session due to user data issue: {str(e)}",
        )
    except Exception as e:
        # DEBUG LOG [ITERATION_1]: Generic error
        logger.error("[DEBUG][ITERATION_1] ❌ EXCEPTION in create_session endpoint")
        logger.error("[DEBUG][ITERATION_1] Exception type: %s", type(e).__name__)
        logger.error("[DEBUG][ITERATION_1] Exception message: %s", str(e))
        logger.error("Failed to create Agent Mode session: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to create session: {str(e)}"
        )


@router.post("/agent/chat")
async def process_command(
    request: ChatRequest,
    controller: AgentModeController = Depends(get_agent_controller),
    current_user: User = Depends(get_current_user),
):
    """
    Process command in Agent Mode with real-time streaming.

    Sends the command to the Aider session and streams the output
    back to the frontend using Server-Sent Events (SSE).

    The stream will include:
    - log events: Real-time output from Aider
    - status events: Completion or error status
    - error events: Error messages if something fails

    Args:
        request: Chat request with command
        controller: AgentModeController instance
        current_user: Authenticated user

    Returns:
        StreamingResponse with SSE events

    Raises:
        HTTPException: If session not found or command fails
    """
    try:
        logger.info(
            "User %s (ID: %s) sending command to session %s",
            current_user.email, current_user.id, request.conversation_id
        )

        async def event_generator():
            """Generate SSE events from controller stream."""
            try:
                async for message in controller.process_command(
                    conversation_id=request.conversation_id, command=request.command
                ):
                    # Format as SSE event
                    event_type = message.get("type", "message")

                    if event_type == "log":
                        # Stream log content
                        content = message.get("content", "")
                        yield f"event: log\ndata: {content}\n\n"

                    elif event_type == "status":
                        # Stream status update
                        status = message.get("status", "unknown")
                        yield f"event: status\ndata: {status}\n\n"

                    elif event_type == "error":
                        # Stream error
                        error_msg = message.get("message", "Unknown error")
                        yield f"event: error\ndata: {error_msg}\n\n"

                # Send completion event
                yield "event: done\ndata: completed\n\n"

            except ValueError as e:
                # Session not found
                logger.error("Session error: %s", e)
                yield f"event: error\ndata: {str(e)}\n\n"

            except Exception as e:
                # Unexpected error
                logger.error("Stream error: %s", e)
                yield f"event: error\ndata: Internal error: {str(e)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except Exception as e:
        logger.error("Failed to process command: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to process command: {str(e)}"
        )


@router.delete("/agent/sessions/{conversation_id}", response_model=dict)
async def close_session(
    conversation_id: str,
    controller: AgentModeController = Depends(get_agent_controller),
    current_user: User = Depends(get_current_user),
):
    """
    Close Agent Mode session gracefully.

    Terminates the Aider process and cleans up resources.

    Args:
        conversation_id: Session identifier to close
        controller: AgentModeController instance
        current_user: Authenticated user

    Returns:
        Closure confirmation

    Raises:
        HTTPException: If session not found or closure fails
    """
    try:
        logger.info("User %s (ID: %s) closing session %s", current_user.email, current_user.id, conversation_id)

        response = await controller.close_session(conversation_id)
        return response

    except ValueError as e:
        logger.error("Session not found: %s", e)
        raise HTTPException(status_code=404, detail=str(e)) from e

    except Exception as e:
        logger.error("Failed to close session: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to close session: {str(e)}"
        )


@router.get("/agent/sessions/{conversation_id}", response_model=dict)
async def get_session_status(
    conversation_id: str,
    controller: AgentModeController = Depends(get_agent_controller),
    _current_user: User = Depends(get_current_user),
):
    """
    Get status of Agent Mode session.

    Args:
        conversation_id: Session identifier
        controller: AgentModeController instance
        current_user: Authenticated user

    Returns:
        Session status information

    Raises:
        HTTPException: If session not found
    """
    try:
        status = await controller.get_session_status(conversation_id)
        return status

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/agent/sessions", response_model=List[dict])
async def list_sessions(
    controller: AgentModeController = Depends(get_agent_controller),
    _current_user: User = Depends(get_current_user),
):
    """
    List all active Agent Mode sessions.

    Args:
        controller: AgentModeController instance
        current_user: Authenticated user

    Returns:
        List of active session information
    """
    sessions = await controller.list_active_sessions()
    return sessions


@router.get("/agent/health", response_model=dict)
async def health_check(controller: AgentModeController = Depends(get_agent_controller)):
    """
    Check health of Aider-Worker service.

    This endpoint does not require authentication and can be used
    for monitoring purposes.

    Args:
        controller: AgentModeController instance

    Returns:
        Health status from Aider-Worker
    """
    health = await controller.health_check()
    return health
