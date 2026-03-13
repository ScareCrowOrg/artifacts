"""
Workflow execution module for orchestrator.

This module handles:
- Executing cell workflows (custom graphs, YAML workflows)
- Loading workflow definitions
- Managing workflow execution strategies
"""

import importlib
import logging
from typing import Any, Dict, Optional

from app.auth_legacy import SYSTEM_USER
from app.config import BASE_DIR
from app.database import db
from app.event_bus import publish_cell_state_changed_sync
from app.models import Agent, Cell, CellStatus, NotebookItemType
from app.workflow_executor import (
    WorkflowState,
    build_workflow_graph,
    find_graph_reference,
    parse_workflow_yaml,
)

from ..helpers import (
    cell_to_pipeline_item,
    publish_pipeline_fragments,
    update_cell_from_pipeline_item,
)

logger = logging.getLogger(__name__)

# Error message templates for workflow contract enforcement
ERROR_MSG_MISSING_EXECUTE = (
    "Workflow module '{module_path}' does not implement required execute(pipeline_item) function. "
    "All custom workflows must adhere to the PipelineItem execution contract. "
    "See docs/official/backend/INGESTION_EXECUTION_CONTRACT.md for details."
)

ERROR_MSG_IMPORT_FAILED = (
    "Failed to import workflow module '{module_path}': {error}. "
    "Ensure the module exists and all dependencies are available."
)

ERROR_MSG_EXECUTION_FAILED = (
    "Workflow execution error in module '{module_path}': {error}. "
    "All workflows must implement execute(pipeline_item) and handle errors properly."
)


class WorkflowExecutor:
    """Handles workflow execution for cells."""

    def __init__(self, state_manager):
        """
        Initialize workflow executor.

        Args:
            state_manager: StateManager instance for cell state updates
        """
        self.state_manager = state_manager
        self.workflow_graph = build_workflow_graph()

    async def execute_cell_workflow(self, cell_id: str) -> bool:
        """
        Execute the workflow for a specific cell.

        Args:
            cell_id: ID of the cell to execute

        Returns:
            True if execution succeeded, False otherwise
        """
        try:
            # Load cell
            cell = await db.find_one(
                "cells", cell_id, current_user=SYSTEM_USER, model_class=Cell
            )
            if not cell:
                logger.error("Cell not found: %s", cell_id)
                return False

            # Update state to RUNNING
            await self.state_manager.update_cell_state(cell_id, CellStatus.RUNNING)

            # Load cell type
            cell_type = await db.find_one(
                "notebook_item_types",
                cell.notebook_item_type_id,
                current_user=SYSTEM_USER,
                model_class=NotebookItemType,
            )

            if not cell_type:
                error_msg = f"Cell type not found: {cell.notebook_item_type_id}"
                logger.error(error_msg)
                await self.state_manager.update_cell_state(
                    cell_id, CellStatus.ERROR, error_data=error_msg
                )
                return False

            # Load agent responsible for this cell
            agent = await db.find_one(
                "agents", cell.assignee_id, current_user=SYSTEM_USER, model_class=Agent
            )

            if not agent:
                logger.warning("Agent not found: %s, continuing without agent context", cell.assignee_id)
                agent_data = {}
            else:
                logger.info("Loaded agent: %s (model: %s)", agent.name, agent.ia_model_id)
                agent_data = {
                    "id": agent.id,
                    "name": agent.name,
                    "ia_model_id": agent.ia_model_id,
                    "agent_type_id": agent.agent_type_id,
                }

            # Convert Cell to PipelineItem
            pipeline_item = cell_to_pipeline_item(cell, agent_data)
            pipeline_item.update_status("running")

            # Track last fragment ID for incremental Redis publishing
            last_fragment_id = (
                pipeline_item.fragments[-1].get("id")
                if pipeline_item.fragments
                else None
            )

            # PRIORITY 1: Check for custom graph file (*graph.py) in default_refs['workflow_graph']
            graph_ref = find_graph_reference(cell_type)

            if graph_ref:
                return await self._execute_custom_graph(
                    cell_id,
                    cell,
                    cell_type,
                    agent_data,
                    pipeline_item,
                    last_fragment_id,
                    graph_ref,
                )

            # PRIORITY 2: Check for YAML workflow file reference
            workflow_def = self._load_workflow_from_yaml(cell_type)

            # PRIORITY 3: Fallback to inline workflow
            if not workflow_def:
                if (
                    not cell_type.workflows
                    or "main_workflow" not in cell_type.workflows
                ):
                    error_msg = "Cell type has no main_workflow defined, no workflow file found, and no custom graph"
                    logger.error(error_msg)
                    await self.state_manager.update_cell_state(
                        cell_id, CellStatus.ERROR, error_data=error_msg
                    )
                    return False

                logger.info("Using inline workflow from cell type: %s", cell_type.name)
                workflow_def = cell_type.workflows["main_workflow"]

            # Execute via LangGraph workflow
            return await self._execute_langgraph_workflow(
                cell_id, cell, agent_data, workflow_def
            )

        except Exception as e:
            logger.error("Error executing cell workflow: %s", e, exc_info=True)
            await self.state_manager.update_cell_state(
                cell_id, CellStatus.ERROR, error_data=str(e)
            )
            return False

    async def _execute_custom_graph(
        self,
        cell_id: str,
        cell: Cell,
        _cell_type: NotebookItemType,
        _agent_data: Dict[str, Any],
        pipeline_item,
        last_fragment_id: Optional[str],
        graph_ref: str,
    ) -> bool:
        """
        Execute workflow using custom graph with PipelineItem.

        All custom workflow modules MUST implement an execute(pipeline_item) function
        that accepts a PipelineItem and returns an updated PipelineItem.

        This enforces the official INGESTION_EXECUTION_CONTRACT.md standard.
        """
        logger.info("Found custom graph reference: %s", graph_ref)

        try:
            logger.info("Loading workflow module for PipelineItem-based execution...")

            # Convert file path to module path
            module_path = (
                graph_ref.replace(str(BASE_DIR) + "/", "")
                .replace("backend/", "")
                .replace(".py", "")
                .replace("/", ".")
            )

            logger.info("Loading module: %s", module_path)
            workflow_module = importlib.import_module(module_path)

            # Check if module has execute() function - THIS IS MANDATORY
            if not hasattr(workflow_module, "execute"):
                error_msg = ERROR_MSG_MISSING_EXECUTE.format(module_path=module_path)
                logger.error(error_msg)
                await self.state_manager.update_cell_state(
                    cell_id, CellStatus.ERROR, error_data=error_msg
                )
                return False

            logger.info("Found execute() function, invoking with PipelineItem...")

            # Execute workflow with PipelineItem
            result_item = workflow_module.execute(pipeline_item)

            # Publish new fragments to Redis
            publish_pipeline_fragments(result_item, since_fragment_id=last_fragment_id)

            # Check for errors
            if result_item.error:
                logger.error("Workflow execution failed: %s", result_item.error)
                await update_cell_from_pipeline_item(cell_id, result_item)
                await self.state_manager.update_cell_state(
                    cell_id, CellStatus.ERROR, error_data=result_item.error
                )
                return False

            # Update cell from PipelineItem
            result_item.update_status("completed")
            await update_cell_from_pipeline_item(cell_id, result_item)

            # Publish final state change
            try:
                cell = await db.find_one(
                    "cells", cell_id, current_user=SYSTEM_USER, model_class=Cell
                )
                cell_data = cell.model_dump() if cell else None
                publish_cell_state_changed_sync(
                    cell_id, CellStatus.COMPLETED.value, cell_data
                )
            except Exception as e:
                logger.warning("Failed to publish state change event: %s", e)

            logger.info("Cell %s workflow completed successfully", cell_id)
            return True

        except ImportError as e:
            error_msg = ERROR_MSG_IMPORT_FAILED.format(
                module_path=module_path, error=str(e)
            )
            logger.error(error_msg, exc_info=True)
            await self.state_manager.update_cell_state(
                cell_id, CellStatus.ERROR, error_data=error_msg
            )
            return False
        except Exception as e:
            error_msg = ERROR_MSG_EXECUTION_FAILED.format(
                module_path=graph_ref, error=str(e)
            )
            logger.error(error_msg, exc_info=True)
            await self.state_manager.update_cell_state(
                cell_id, CellStatus.ERROR, error_data=error_msg
            )
            return False

    def _load_workflow_from_yaml(self, cell_type: NotebookItemType) -> Optional[str]:
        """Load workflow definition from YAML file reference."""
        if not cell_type.yaml_refs:
            return None

        for yaml_ref in cell_type.yaml_refs:
            if "workflow" in yaml_ref.lower():
                workflow_file = BASE_DIR / yaml_ref
                if workflow_file.exists():
                    logger.info("Loading workflow from file: %s", workflow_file)
                    try:
                        with open(workflow_file, "r") as f:
                            workflow_def = f.read()
                        logger.info("Successfully loaded workflow from %s", yaml_ref)
                        return workflow_def
                    except Exception as e:
                        logger.error("Error reading workflow file %s: %s", yaml_ref, e)
                else:
                    logger.warning("Workflow file not found: %s", workflow_file)

        return None

    async def _execute_langgraph_workflow(
        self, cell_id: str, cell: Cell, agent_data: Dict[str, Any], workflow_def: str
    ) -> bool:
        """Execute workflow using standard LangGraph workflow."""
        # Parse workflow
        logger.info("Parsing workflow for cell")
        workflow_steps = parse_workflow_yaml(workflow_def)

        # Build initial state for LangGraph
        initial_state: WorkflowState = {
            "cell_id": cell_id,
            "cell_data": cell.initial_data,
            "agent_data": agent_data,
            "workflow_steps": workflow_steps,
            "current_step_index": 0,
            "step_outputs": {},
            "error": None,
            "completed": False,
        }

        # Execute workflow using LangGraph
        logger.info("Executing workflow with %s steps", len(workflow_steps))
        final_state = self.workflow_graph.invoke(initial_state)

        # Check result
        if final_state["error"]:
            logger.error("Workflow failed: %s", final_state['error'])
            await self.state_manager.update_cell_state(
                cell_id, CellStatus.ERROR, error_data=final_state["error"]
            )
            return False

        # Extract outputs
        output_data = {}
        for key, value in final_state["step_outputs"].items():
            if isinstance(value, dict) and "stdout" in value:
                # Extract path from stdout
                stdout_lines = value["stdout"].strip().split("\n")
                if stdout_lines:
                    output_data[f"{key}_path"] = stdout_lines[-1]
            else:
                output_data[key] = value

        # Update state to COMPLETED
        await self.state_manager.update_cell_state(
            cell_id, CellStatus.COMPLETED, output_data=output_data
        )

        logger.info("Cell %s workflow completed successfully", cell_id)
        return True
