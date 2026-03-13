"""
Main Orchestrator facade class.

This module provides a unified interface to the orchestrator functionality,
delegating to specialized modules for state management, workflow execution,
and queue monitoring.

Technical naming: All method names and parameters in English.
"""

import logging
from typing import Any, Dict, List

from app.auth_legacy import SYSTEM_USER
from app.database import db
from app.models import Agent, Book, Cell, CellStatus

from .monitoring import QueueMonitor
from .state_manager import StateManager
from .workflow_executor import WorkflowExecutor

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main orchestrator class for managing cell workflow execution.

    Responsibilities:
    - Monitor issues-queue for PENDING cells
    - Load and parse workflow definitions
    - Execute workflows using LangGraph
    - Manage cell state transitions
    """

    def __init__(self, agent_id: str = "main-workflow-orchestrator-v1"):
        """
        Initialize the orchestrator (synchronous initialization).

        Note: The agent and issues_queue are loaded lazily on first use
        or via the async initialize() method.

        Args:
            agent_id: ID of the orchestrator agent
        """
        self.agent_id = agent_id
        self.agent = None
        self.issues_queue = None

        # Default config (will be updated when agent is loaded)
        self.polling_interval = 5
        self.max_concurrent_cells = 2

        # Initialize specialized modules
        self.state_manager = StateManager()
        self.workflow_executor = WorkflowExecutor(self.state_manager)
        self.queue_monitor = None  # Will be initialized after loading

        logger.info("Orchestrator created with agent_id: %s", agent_id)

    async def initialize(self):
        """
        Async initialization method to load data from database.

        This should be called after creating the Orchestrator instance
        to load the agent and issues queue from the database.
        """
        self.agent = await self._load_agent()
        self.issues_queue = await self._load_issues_queue()

        # Get config from agent
        config = self.agent.agent_specific_config
        self.polling_interval = config.get("polling_interval_seconds", 5)
        self.max_concurrent_cells = config.get("max_concurrent_cells", 2)

        # Initialize queue monitor with loaded data
        self.queue_monitor = QueueMonitor(
            self.issues_queue,
            self.workflow_executor,
            self.polling_interval,
            self.max_concurrent_cells,
        )

        logger.info("Orchestrator initialized: %s", self.agent.name)
        logger.info("Polling interval: %ss", self.polling_interval)
        logger.info("Max concurrent cells: %s", self.max_concurrent_cells)

    async def _ensure_agent_exists(self) -> None:
        """Create default orchestrator agent if it doesn't exist."""
        agent = await db.find_one(
            "agents", self.agent_id, current_user=SYSTEM_USER, model_class=Agent
        )

        if agent:
            return  # Agent already exists

        logger.warning("Orchestrator agent not found: %s. Creating default agent...", self.agent_id)

        # Create default orchestrator agent
        default_agent = Agent(
            id=self.agent_id,
            name="Main Workflow Orchestrator",
            description="Default orchestrator agent for managing cell workflow execution",
            agent_type_id="orchestrator-v1",
            ia_model_id="gpt-4",  # Default model
            persona_definitions={
                "role": "workflow_orchestrator",
                "capabilities": ["task_routing", "cell_execution", "state_management"],
            },
            agent_specific_config={
                "max_retries": 3,
                "timeout_seconds": 300,
                "enable_logging": True,
            },
            is_active=True,
            version="1.0.0",
        )

        # Persist to database using SYSTEM_USER
        await db.insert("agents", default_agent, current_user=SYSTEM_USER)
        logger.info("Created default orchestrator agent: %s", self.agent_id)

    async def _load_agent(self) -> Agent:
        """Load the orchestrator agent from database (read from filesystem via HybridDatabase)."""
        # Ensure agent exists before trying to load
        await self._ensure_agent_exists()

        agent = await db.find_one(
            "agents", self.agent_id, current_user=SYSTEM_USER, model_class=Agent
        )

        if not agent:
            raise ValueError(f"Orchestrator agent not found: {self.agent_id}")

        logger.info("Loaded agent: %s", agent.name)
        return agent

    async def _load_issues_queue(self) -> Book:
        """Load the issues-queue book from database (read from filesystem via HybridDatabase)."""
        book = await db.find_one(
            "books", "book-issues-queue-v1", current_user=SYSTEM_USER, model_class=Book
        )

        if not book:
            raise ValueError("issues-queue book not found")

        logger.info("Loaded book: %s with %s cells", book.name, len(book.cells))
        return book

    # ========================================
    # Delegation methods to QueueMonitor
    # ========================================

    async def get_pending_cells(self) -> List[Cell]:
        """
        Get all PENDING cells whose source_book_id matches the issues-queue book.

        Returns:
            List of PENDING Cell instances
        """
        return await self.queue_monitor.get_pending_cells()

    def start_monitoring(self) -> Dict[str, Any]:
        """
        Start the async monitoring loop as a background task.

        Returns:
            Dict with status message
        """
        return self.queue_monitor.start_monitoring()

    def stop_monitoring(self) -> Dict[str, Any]:
        """
        Stop the async monitoring loop.

        Returns:
            Dict with status message
        """
        return self.queue_monitor.stop_monitoring()

    def get_monitoring_status(self) -> Dict[str, Any]:
        """
        Get current monitoring status.

        Returns:
            Dict with monitoring status information
        """
        return self.queue_monitor.get_monitoring_status()

    def pause_processing(self) -> Dict[str, Any]:
        """
        Pause cell processing.

        Returns:
            Dict with status message
        """
        return self.queue_monitor.pause_processing()

    def resume_processing(self) -> Dict[str, Any]:
        """
        Resume cell processing.

        Returns:
            Dict with status message
        """
        return self.queue_monitor.resume_processing()

    def get_processing_status(self) -> Dict[str, Any]:
        """
        Get current processing status.

        Returns:
            Dict with processing status information
        """
        return self.queue_monitor.get_processing_status()

    async def force_process_pending_issues(self) -> Dict[str, Any]:
        """
        Force immediate processing of pending issues.

        Returns:
            Dict with status and number of pending cells found
        """
        return await self.queue_monitor.force_process_pending_issues()

    async def monitor_queue_async(self):
        """
        Async monitoring loop with manual trigger support.

        Continuously polls the issues-queue for PENDING cells
        and executes their workflows.
        """
        return await self.queue_monitor.monitor_queue_async()

    async def monitor_queue(self):
        """
        Main monitoring loop (async version).

        Continuously polls the issues-queue for PENDING cells
        and executes their workflows.
        """
        return await self.queue_monitor.monitor_queue()

    # ========================================
    # Delegation methods to StateManager
    # ========================================

    async def update_cell_state(
        self,
        cell_id: str,
        new_state: CellStatus,
        output_data: Dict[str, Any] = None,
        error_data: str = None,
    ) -> bool:
        """
        Update cell state in the database.

        Args:
            cell_id: ID of the cell to update
            new_state: New state for the cell
            output_data: Optional output data to merge into cell.data
            error_data: Optional error message

        Returns:
            True if update succeeded, False otherwise
        """
        return await self.state_manager.update_cell_state(
            cell_id, new_state, output_data, error_data
        )

    # ========================================
    # Delegation methods to WorkflowExecutor
    # ========================================

    async def execute_cell_workflow(self, cell_id: str) -> bool:
        """
        Execute the workflow for a specific cell.

        Args:
            cell_id: ID of the cell to execute

        Returns:
            True if execution succeeded, False otherwise
        """
        return await self.workflow_executor.execute_cell_workflow(cell_id)
