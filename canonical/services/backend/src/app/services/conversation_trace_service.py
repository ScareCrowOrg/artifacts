"""
Conversation Trace Service - Structured tracing for RAG pipeline observability.

This service manages structured conversation traces by creating trace cells and recording
fragments at each stage of the conversation workflow. It provides:
- Trace cell creation for conversations
- Fragment recording at pipeline stages
- Conversation ID generation
- Global enable/disable flag support

Technical naming: All functions and variables in English.
Documentation: Can be in Portuguese or English.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from ..config import ENABLE_CONVERSATION_TRACING
from ..database import db
from ..models.base import CellStatus
from ..models.content import Cell

logger = logging.getLogger(__name__)


class ConversationTraceService:
    """
    Service for managing structured conversation traces.

    Responsibilities:
    - Create trace cells for conversations
    - Record fragments at each pipeline stage
    - Generate unique conversation IDs
    - Respect global tracing configuration

    Usage:
        service = get_conversation_trace_service()
        if service.is_tracing_enabled():
            conv_id = service.generate_conversation_id()
            trace_cell = await service.create_trace_cell(conv_id, user_id)
            await service.record_fragment(trace_cell.id, "stage_name", data, conv_id)
    """

    def __init__(self):
        """Initialize the conversation trace service."""
        self.trace_book_id = "book-conversation-traces-v1"
        self.trace_type_id = "conversation-trace-item"
        self._tracing_enabled = ENABLE_CONVERSATION_TRACING

    def is_tracing_enabled(self) -> bool:
        """
        Check if conversation tracing is globally enabled.

        Returns:
            True if tracing is enabled, False otherwise
        """
        return self._tracing_enabled

    def generate_conversation_id(self, session_id: Optional[str] = None) -> str:
        """
        Generate a unique conversation ID.

        Args:
            session_id: Optional session ID to incorporate into the conversation ID

        Returns:
            Unique conversation ID string in format:
            - With session: "conv_{session_id}_{short_uuid}"
            - Without session: "conv_{full_uuid}"

        Examples:
            >>> service = ConversationTraceService()
            >>> conv_id = service.generate_conversation_id()
            >>> assert conv_id.startswith("conv_")
            >>> conv_id_with_session = service.generate_conversation_id("sess_123")
            >>> assert "sess_123" in conv_id_with_session
        """
        if session_id:
            return f"conv_{session_id}_{uuid.uuid4().hex[:8]}"
        return f"conv_{uuid.uuid4().hex}"

    async def create_trace_cell(
        self,
        conversation_id: str,
        assignee_id: str,
        session_id: Optional[str] = None,
        user_message: Optional[str] = None,
        target_llm: Optional[str] = None,
    ) -> Optional[Cell]:
        """
        Create a new trace cell for a conversation.

        Args:
            conversation_id: Unique identifier for the conversation
            assignee_id: User ID responsible for the conversation
            session_id: Optional session ID
            user_message: Original user message that started the conversation
            target_llm: Target LLM for the conversation (openai, gemini, ollama)

        Returns:
            Created Cell instance or None if tracing is disabled

        Raises:
            Exception: If database operation fails (logged but not re-raised)

        Examples:
            >>> service = get_conversation_trace_service()
            >>> trace_cell = await service.create_trace_cell(
            ...     conversation_id="conv_abc123",
            ...     assignee_id="user_456",
            ...     user_message="How do I create a cell?"
            ... )
            >>> assert trace_cell is not None
            >>> assert trace_cell.initial_data["conversation_id"] == "conv_abc123"
        """
        if not self.is_tracing_enabled():
            logger.debug(
                "[ConversationTrace] Tracing disabled, skipping trace cell creation"
            )
            return None

        try:
            logger.info("[ConversationTrace] Creating trace cell - conversation_id: %s, assignee: %s, session: %s, target_llm: %s", conversation_id, assignee_id, session_id, target_llm)

            # Create initial data with conversation metadata
            initial_data = {
                "conversation_id": conversation_id,
                "session_id": session_id,
                "tracing_enabled": True,
                "user_message": user_message,
                "target_llm": target_llm,
                "created_at": datetime.utcnow().isoformat(),
            }

            # Create trace cell instance
            trace_cell = Cell(
                assignee_id=assignee_id,
                notebook_item_type_id=self.trace_type_id,
                source_book_id=self.trace_book_id,
                initial_data=initial_data,
                fragments=[],
                status=CellStatus.PENDING,
            )

            logger.debug(
                "[ConversationTrace] Trace cell object created with ID: %s, book: %s, type: %s",
                trace_cell.id, self.trace_book_id, self.trace_type_id
            )

            # Insert into database
            logger.debug("[ConversationTrace] Inserting trace cell into database...")
            db.insert("cells", trace_cell, current_user=SYSTEM_USER)

            logger.info(
                "[ConversationTrace] ✓ SUCCESS: Created trace cell: %s for conversation: %s",
                trace_cell.id, conversation_id
            )

            return trace_cell

        except Exception as e:
            logger.error(
                "[ConversationTrace] ✗ FAILED: Error creating trace cell for conversation %s: %s",
                conversation_id, e, exc_info=True
            )
            return None

    async def record_fragment(
        self, trace_cell_id: str, stage: str, data: Dict[str, Any], conversation_id: str
    ) -> bool:
        """
        Record a trace fragment for a specific pipeline stage.

        Args:
            trace_cell_id: ID of the trace cell to add fragment to
            stage: Stage identifier (e.g., 'initial_prompt', 'rag_retrieval', 'llm_response')
            data: Stage-specific data to record (should be JSON-serializable)
            conversation_id: Conversation ID for validation

        Returns:
            True if fragment was recorded successfully, False otherwise

        Raises:
            Does not raise exceptions; logs errors and returns False

        Examples:
            >>> service = get_conversation_trace_service()
            >>> success = await service.record_fragment(
            ...     trace_cell_id="cell_123",
            ...     stage="rag_retrieval",
            ...     data={"chunks_retrieved": 5, "query": "test"},
            ...     conversation_id="conv_abc"
            ... )
            >>> assert success is True
        """
        if not self.is_tracing_enabled():
            logger.debug(
                "[ConversationTrace] Tracing disabled, skipping fragment recording"
            )
            return False

        try:
            logger.info(
                "[ConversationTrace] Recording fragment - stage: '%s', trace_cell_id: %s, conversation_id: %s",
                stage, trace_cell_id, conversation_id
            )

            # Construct fragment with timestamp and metadata
            fragment = {
                "timestamp": datetime.utcnow().isoformat(),
                "conversation_id": conversation_id,
                "stage": stage,
                "data": data,
            }

            logger.debug("[ConversationTrace] Fragment data size: %s chars", len(str(data)))

            # Retrieve trace cell from database
            logger.debug("[ConversationTrace] Retrieving trace cell %s from database", trace_cell_id)
            trace_cell = db.find_one("cells", trace_cell_id, Cell, is_canonical=False)
            if not trace_cell:
                logger.error("[ConversationTrace] FAILED: Trace cell not found: %s", trace_cell_id)
                return False

            logger.debug(
                "[ConversationTrace] Retrieved trace cell %s, current fragments: %s",
                trace_cell_id, len(trace_cell.fragments)
            )

            # Append fragment to existing fragments list
            updated_fragments = trace_cell.fragments + [fragment]

            # Update cell in database
            logger.debug("[ConversationTrace] Updating cell with %s fragments", len(updated_fragments))
            db.update(
                "cells",
                trace_cell_id,
                {"fragments": updated_fragments},
                is_canonical=False,
            )

            logger.info(
                "[ConversationTrace] ✓ SUCCESS: Recorded fragment for stage '%s' in trace %s (total fragments: %s)",
                stage, trace_cell_id, len(updated_fragments)
            )
            return True

        except Exception as e:
            logger.error(
                "[ConversationTrace] ✗ FAILED: Error recording fragment for stage '%s': %s",
                stage, e, exc_info=True
            )
            return False


# Singleton instance for service
_trace_service: Optional[ConversationTraceService] = None


def get_conversation_trace_service() -> ConversationTraceService:
    """
    Get or create the conversation trace service singleton.

    Returns:
        Singleton instance of ConversationTraceService

    Examples:
        >>> service = get_conversation_trace_service()
        >>> assert isinstance(service, ConversationTraceService)
        >>> service2 = get_conversation_trace_service()
        >>> assert service is service2  # Same instance
    """
    global _trace_service
    if _trace_service is None:
        _trace_service = ConversationTraceService()
    return _trace_service
