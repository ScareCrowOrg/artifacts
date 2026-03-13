"""
Queue monitoring module for orchestrator.

This module handles:
- Async and sync queue monitoring loops
- Monitoring control (start, stop, pause, resume)
- Manual trigger support for immediate processing
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.auth_legacy import SYSTEM_USER
from app.database import db
from app.models import Book, Cell, CellStatus

logger = logging.getLogger(__name__)


class QueueMonitor:
    """Handles queue monitoring and processing control."""

    def __init__(
        self,
        issues_queue: Book,
        workflow_executor,
        polling_interval: int = 5,
        max_concurrent_cells: int = 2,
    ):
        """
        Initialize queue monitor.

        Args:
            issues_queue: Issues queue book to monitor
            workflow_executor: WorkflowExecutor instance for executing cells
            polling_interval: Seconds between polling cycles
            max_concurrent_cells: Maximum cells to process concurrently
        """
        self.issues_queue = issues_queue
        self.workflow_executor = workflow_executor
        self.polling_interval = polling_interval
        self.max_concurrent_cells = max_concurrent_cells

        # Event for manual triggering
        self.process_trigger_event = asyncio.Event()

        # Monitoring control
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None

        # Processing control (pause/resume)
        self.processing_paused = False

    async def get_pending_cells(self) -> List[Cell]:
        """
        Get all PENDING cells whose origemLivroId matches the issues-queue book.

        Returns:
            List of PENDING Cell instances
        """
        try:
            # Get all cells from runtime data
            all_cells = await db.find_many(
                "cells", current_user=SYSTEM_USER, model_class=Cell
            )
            # Filter by source_book_id and PENDING state
            pending_cells = [
                cell
                for cell in all_cells
                if cell.source_book_id == self.issues_queue.id
                and cell.status == CellStatus.PENDING
            ]
            logger.info("Found %s pending cells", len(pending_cells))
            return pending_cells
        except Exception as e:
            logger.error("Error fetching pending cells: %s", e)
            return []

    def start_monitoring(self) -> Dict[str, Any]:
        """
        Start the async monitoring loop as a background task.

        Returns:
            Dict with status message
        """
        try:
            if self.monitoring_active:
                return {
                    "status": "already_running",
                    "message": "Monitoring is already active",
                }

            self.monitoring_active = True

            # Create monitoring task - requires an async context with running event loop
            try:
                # Verify we're in an async context by attempting to get the running loop
                # This call raises RuntimeError if no loop is running
                asyncio.get_running_loop()
                # Use asyncio.create_task() which automatically uses the currently running loop
                # (guaranteed to exist since get_running_loop() succeeded)
                self.monitoring_task = asyncio.create_task(self.monitor_queue_async())
            except RuntimeError as e:
                # No active asyncio event loop found - cannot start monitoring
                # This means start_monitoring() was called from a synchronous context
                self.monitoring_active = False
                raise RuntimeError(
                    "start_monitoring() requires an async context with running event loop. "
                    "Called from synchronous context. "
                    "For standalone execution, use monitor_queue() instead."
                ) from e

            logger.info("Monitoring loop started")
            return {
                "status": "started",
                "message": "Monitoring loop started successfully",
            }

        except Exception as e:
            logger.error("Error starting monitoring: %s", e, exc_info=True)
            self.monitoring_active = False
            return {"status": "error", "message": str(e)}

    def stop_monitoring(self) -> Dict[str, Any]:
        """
        Stop the async monitoring loop.

        Returns:
            Dict with status message
        """
        try:
            if not self.monitoring_active:
                return {"status": "not_running", "message": "Monitoring is not active"}

            self.monitoring_active = False

            # Cancel monitoring task
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                logger.info("Monitoring task cancelled")

            logger.info("Monitoring loop stopped")
            return {
                "status": "stopped",
                "message": "Monitoring loop stopped successfully",
            }

        except Exception as e:
            logger.error("Error stopping monitoring: %s", e, exc_info=True)
            return {"status": "error", "message": str(e)}

    def get_monitoring_status(self) -> Dict[str, Any]:
        """
        Get current monitoring status.

        Returns:
            Dict with monitoring status information
        """
        return {
            "active": self.monitoring_active,
            "polling_interval": self.polling_interval,
            "max_concurrent_cells": self.max_concurrent_cells,
            "task_running": (
                self.monitoring_task is not None and not self.monitoring_task.done()
                if self.monitoring_task
                else False
            ),
        }

    def pause_processing(self) -> Dict[str, Any]:
        """
        Pause cell processing.

        Returns:
            Dict with status message
        """
        try:
            if self.processing_paused:
                return {
                    "status": "already_paused",
                    "message": "Processing is already paused",
                }

            self.processing_paused = True
            logger.info("Cell processing paused")

            return {
                "status": "paused",
                "message": "Cell processing paused successfully",
            }

        except Exception as e:
            logger.error("Error pausing processing: %s", e, exc_info=True)
            return {"status": "error", "message": str(e)}

    def resume_processing(self) -> Dict[str, Any]:
        """
        Resume cell processing.

        Returns:
            Dict with status message
        """
        try:
            if not self.processing_paused:
                return {"status": "not_paused", "message": "Processing is not paused"}

            self.processing_paused = False
            logger.info("Cell processing resumed")

            return {
                "status": "resumed",
                "message": "Cell processing resumed successfully",
            }

        except Exception as e:
            logger.error("Error resuming processing: %s", e, exc_info=True)
            return {"status": "error", "message": str(e)}

    def get_processing_status(self) -> Dict[str, Any]:
        """
        Get current processing status.

        Returns:
            Dict with processing status information
        """
        return {"paused": self.processing_paused}

    async def force_process_pending_issues(self) -> Dict[str, Any]:
        """
        Force immediate processing of pending issues.

        Returns:
            Dict with status and number of pending cells found
        """
        try:
            logger.info(
                "Manual trigger: forcing immediate processing of pending issues"
            )

            # Get pending cells
            pending_cells = await self.get_pending_cells()
            pending_count = len(pending_cells)

            logger.info("Manual trigger found %s pending cells", pending_count)

            if pending_count == 0:
                return {
                    "status": "no_pending_cells",
                    "message": "No pending cells to process",
                    "pending_count": 0,
                }

            # Set the event to trigger immediate processing
            self.process_trigger_event.set()

            return {
                "status": "processing_triggered",
                "message": f"Triggered processing of {pending_count} pending cells",
                "pending_count": pending_count,
            }

        except Exception as e:
            logger.error("Error in force_process_pending_issues: %s", e, exc_info=True)
            return {"status": "error", "message": str(e), "pending_count": 0}

    async def monitor_queue_async(self):
        """
        Async monitoring loop with manual trigger support.

        Continuously polls the issues-queue for PENDING cells
        and executes their workflows.
        """
        logger.info("Starting async queue monitoring loop...")

        try:
            while self.monitoring_active:
                # Check if processing is paused
                if self.processing_paused:
                    logger.debug("Processing is paused, skipping cell processing")
                else:
                    # Get pending cells
                    pending_cells = await self.get_pending_cells()

                    if pending_cells:
                        logger.info("Found %s pending cells", len(pending_cells))

                        # Process cells (respecting max_concurrent_cells)
                        for cell in pending_cells[: self.max_concurrent_cells]:
                            # Double-check pause status before processing each cell
                            if self.processing_paused:
                                logger.info(
                                    "Processing paused during cell iteration, stopping"
                                )
                                break
                            logger.info("Processing cell: %s", cell.id)
                            await self.workflow_executor.execute_cell_workflow(cell.id)

                # Clear the trigger event if it was set
                if self.process_trigger_event.is_set():
                    logger.info("Clearing manual trigger event")
                    self.process_trigger_event.clear()

                # Wait for either the polling interval or a manual trigger
                try:
                    await asyncio.wait_for(
                        self.process_trigger_event.wait(), timeout=self.polling_interval
                    )
                    logger.info("Manual trigger event received, processing immediately")
                except asyncio.TimeoutError:
                    # Normal timeout, continue with regular polling
                    pass

            logger.info("Monitoring loop stopped (monitoring_active=False)")

        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
            raise
        except Exception as e:
            logger.error("Error in monitoring loop: %s", e, exc_info=True)
            self.monitoring_active = False
            raise

    async def monitor_queue(self):
        """
        Main monitoring loop (async version for standalone execution).

        Continuously polls the issues-queue for PENDING cells
        and executes their workflows.
        """
        logger.info("Starting queue monitoring loop...")

        try:
            while True:
                # Get pending cells
                pending_cells = await self.get_pending_cells()

                if pending_cells:
                    logger.info("Found %s pending cells", len(pending_cells))

                    # Process cells (respecting max_concurrent_cells)
                    for cell in pending_cells[: self.max_concurrent_cells]:
                        logger.info("Processing cell: %s", cell.id)
                        await self.workflow_executor.execute_cell_workflow(cell.id)

                # Sleep before next poll
                await asyncio.sleep(self.polling_interval)

        except KeyboardInterrupt:
            logger.info("Monitoring loop interrupted by user")
        except Exception as e:
            logger.error("Error in monitoring loop: %s", e, exc_info=True)
            raise
