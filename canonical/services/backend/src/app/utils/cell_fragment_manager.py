#!/usr/bin/env python3
"""
Cell Fragment Manager

This module provides utilities for managing fragments and status updates
for cells in the ScareVerse system. It acts as a centralized interface
for adding execution and memory fragments to cells and updating their status
with proper traceability.

The CellFragmentManager integrates with the database layer to ensure
fragments are persisted correctly and provides a consistent API for
workflow components.

Usage:
    from app.utils.cell_fragment_manager import CellFragmentManager

    manager = CellFragmentManager()
    await manager.add_memory_fragment(
        cell_id="abc123",
        content="Important context information",
        metadata={"source": "workflow_node"}
    )
"""

import logging
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from app.database import db

logger = logging.getLogger(__name__)


class CellFragmentManager:
    """
    Manager for adding fragments and updating status of cells.

    This class provides a high-level interface for fragment management,
    ensuring consistency and traceability across the ingestion workflow
    and other cell-based operations.
    """

    def __init__(self):
        """Initialize the CellFragmentManager."""
        self.db = db

    async def add_memory_fragment(
        self,
        cell_id: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Add a memory fragment to a cell.

        Memory fragments represent contextual information, state snapshots,
        or important data that should be preserved for future reference.

        Args:
            cell_id: ID of the cell to update
            content: Content of the fragment (can be string, dict, etc.)
            metadata: Optional metadata for the fragment
            user_id: Optional user ID for database filtering
            session_id: Optional session ID for database filtering

        Returns:
            True if fragment was added successfully, False otherwise

        Example:
            success = await manager.add_memory_fragment(
                cell_id="cell123",
                content={"document_id": "doc456", "status": "processed"},
                metadata={"workflow": "ingestion", "step": "finalize"}
            )
        """
        try:
            # Create fragment dictionary
            fragment = {
                "tipo": "memoria",
                "conteudo": content,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if metadata:
                fragment["metadata"] = metadata

            # Add fragment to cell using database $push operation
            success = await self.db.update(
                collection="celulas",
                doc_id=cell_id,
                updates={"$push": {"fragmentos": fragment}},
                user_id=user_id,
                session_id=session_id,
            )

            if success:
                logger.debug("Memory fragment added to cell %s", cell_id)
            else:
                logger.warning("Failed to add memory fragment to cell %s", cell_id)

            return success

        except Exception as e:
            logger.error("Error adding memory fragment to cell %s: %s", cell_id, e)
            return False

    async def add_result_fragment(
        self,
        cell_id: str,
        content: Any,
        result: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Add an execution result fragment to a cell.

        Result fragments represent the outcome of operations, including
        success messages, error details, or execution summaries.

        Args:
            cell_id: ID of the cell to update
            content: Description or message about the execution
            result: Optional result data from the operation
            metadata: Optional metadata for the fragment
            user_id: Optional user ID for database filtering
            session_id: Optional session ID for database filtering

        Returns:
            True if fragment was added successfully, False otherwise

        Example:
            success = await manager.add_result_fragment(
                cell_id="cell123",
                content="Preprocessing completed successfully",
                result={"chunks_created": 42, "duration_ms": 1234},
                metadata={"step": "preprocess_and_chunk"}
            )
        """
        try:
            # Create fragment dictionary
            fragment = {
                "tipo": "execucao",
                "conteudo": content,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if result is not None:
                fragment["resultado"] = result

            if metadata:
                fragment["metadata"] = metadata

            # Add fragment to cell using database $push operation
            success = await self.db.update(
                collection="celulas",
                doc_id=cell_id,
                updates={"$push": {"fragmentos": fragment}},
                user_id=user_id,
                session_id=session_id,
            )

            if success:
                logger.debug("Result fragment added to cell %s", cell_id)
            else:
                logger.warning("Failed to add result fragment to cell %s", cell_id)

            return success

        except Exception as e:
            logger.error("Error adding result fragment to cell %s: %s", cell_id, e)
            return False

    async def update_status_with_fragment(
        self,
        cell_id: str,
        new_status: Literal["pending", "running", "completed", "error"],
        fragment_content: str,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Update cell status and add a corresponding fragment in one operation.

        This method combines status update with fragment creation to ensure
        traceability of status changes. The fragment will include the status
        transition information.

        Args:
            cell_id: ID of the cell to update
            new_status: New status value (pending, running, completed, error)
            fragment_content: Description of the status change
            metadata: Optional metadata for the fragment
            error_message: Optional error message (for error status)
            user_id: Optional user ID for database filtering
            session_id: Optional session ID for database filtering

        Returns:
            True if both status and fragment were updated successfully

        Example:
            success = await manager.update_status_with_fragment(
                cell_id="cell123",
                new_status="running",
                fragment_content="Ingestion workflow started",
                metadata={"workflow": "ingestion", "transition": "pending->running"}
            )
        """
        try:
            # Create status transition fragment
            fragment = {
                "tipo": "execucao",
                "conteudo": fragment_content,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {},
            }

            # Add status transition info to metadata
            fragment["metadata"]["status_update"] = new_status

            # Prepare update operations
            updates = {
                "$set": {
                    "status": new_status,
                    "updated_at": datetime.utcnow().isoformat(),
                },
                "$push": {"fragmentos": fragment},
            }

            # Add error message if provided
            if error_message and new_status == "error":
                updates["$set"]["error"] = error_message

            # Execute combined update
            success = await self.db.update(
                collection="celulas",
                doc_id=cell_id,
                updates=updates,
                user_id=user_id,
                session_id=session_id,
            )

            if success:
                logger.info("Cell %s status updated to '%s' with fragment", cell_id, new_status)
            else:
                logger.warning("Failed to update status for cell %s", cell_id)

            return success

        except Exception as e:
            logger.error("Error updating status for cell %s: %s", cell_id, e)
            return False

    async def add_fragment(
        self,
        cell_id: str,
        fragment_type: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Add a generic fragment to a cell.

        This is a flexible method that allows adding fragments of any type.
        For specific use cases, prefer add_memory_fragment() or
        add_result_fragment().

        Args:
            cell_id: ID of the cell to update
            fragment_type: Type of fragment (e.g., 'memoria', 'execucao', 'log')
            content: Content of the fragment
            metadata: Optional metadata for the fragment
            result: Optional result data
            user_id: Optional user ID for database filtering
            session_id: Optional session ID for database filtering

        Returns:
            True if fragment was added successfully, False otherwise
        """
        try:
            # Create fragment dictionary
            fragment = {
                "tipo": fragment_type,
                "conteudo": content,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if metadata:
                fragment["metadata"] = metadata

            if result is not None:
                fragment["resultado"] = result

            # Add fragment to cell using database $push operation
            success = await self.db.update(
                collection="celulas",
                doc_id=cell_id,
                updates={"$push": {"fragmentos": fragment}},
                user_id=user_id,
                session_id=session_id,
            )

            if success:
                logger.debug("Fragment of type '%s' added to cell %s", fragment_type, cell_id)
            else:
                logger.warning("Failed to add fragment to cell %s", cell_id)

            return success

        except Exception as e:
            logger.error("Error adding fragment to cell %s: %s", cell_id, e)
            return False


# Singleton instance for convenience
_manager_instance: Optional[CellFragmentManager] = None


def get_cell_fragment_manager() -> CellFragmentManager:
    """
    Get or create the singleton CellFragmentManager instance.

    Returns:
        CellFragmentManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = CellFragmentManager()
    return _manager_instance
