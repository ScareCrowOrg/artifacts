"""
Workflow execution utilities for the Agent Orchestrator.

This module provides functions for parsing workflow YAML definitions,
resolving template variables, executing workflow steps using LangGraph,
and running external scripts.
"""

import logging
import subprocess
import yaml
import re
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from typing import TypedDict

from app.config import BASE_DIR

logger = logging.getLogger(__name__)


# ============================================================================
# LangGraph State Definition
# ============================================================================


class WorkflowState(TypedDict):
    """State for workflow execution in LangGraph."""

    cell_id: str
    cell_data: Dict[str, Any]
    agent_data: Dict[str, Any]
    workflow_steps: List[Dict[str, Any]]
    current_step_index: int
    step_outputs: Dict[str, Any]
    error: Optional[str]
    completed: bool


# ============================================================================
# Script Execution Tool
# ============================================================================


def run_script_tool(script_path: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute an external Python script with provided inputs.

    This function acts as a LangGraph tool to run external scripts
    (like preprocess_and_chunk.py) and capture their outputs.

    Args:
        script_path: Relative path to the script from BASE_DIR
        inputs: Dictionary of input parameters for the script

    Returns:
        Dictionary containing:
        - success: Boolean indicating if execution succeeded
        - stdout: Standard output from the script
        - stderr: Standard error from the script
        - return_code: Process return code
    """
    try:
        # Resolve script path relative to BASE_DIR
        full_script_path = BASE_DIR / script_path

        if not full_script_path.exists():
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Script not found: {full_script_path}",
                "return_code": 1,
            }

        # Build command line arguments from inputs
        cmd = ["python3", str(full_script_path)]

        for key, value in inputs.items():
            # Convert input keys to command-line flags (snake_case to kebab-case)
            flag = f"--{key.replace('_', '-')}"
            cmd.extend([flag, str(value)])

        logger.info("Executing script: %s", ' '.join(cmd))

        # Execute script
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
        )

        logger.info("Script completed with return code: %s", result.returncode)

        if result.stdout:
            logger.debug("Script stdout: %s", result.stdout[:500])
        if result.stderr:
            logger.debug("Script stderr: %s", result.stderr[:500])

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        logger.error("Script execution timed out: %s", script_path)
        return {
            "success": False,
            "stdout": "",
            "stderr": "Script execution timed out after 5 minutes",
            "return_code": -1,
        }
    except Exception as e:
        logger.error("Error executing script %s: %s", script_path, e)
        return {"success": False, "stdout": "", "stderr": str(e), "return_code": -1}


# ============================================================================
# Workflow Parsing and Template Resolution
# ============================================================================


def parse_workflow_yaml(workflow_yaml: str) -> List[Dict[str, Any]]:
    """
    Parse workflow YAML string into a list of step dictionaries.

    Args:
        workflow_yaml: YAML string containing workflow definition

    Returns:
        List of workflow step dictionaries

    Raises:
        ValueError: If YAML is invalid or missing required fields
    """
    try:
        workflow_data = yaml.safe_load(workflow_yaml)

        if not isinstance(workflow_data, dict):
            raise ValueError("Workflow YAML must be a dictionary")

        if "steps" not in workflow_data:
            raise ValueError("Workflow YAML must contain 'steps' key")

        steps = workflow_data["steps"]

        if not isinstance(steps, list):
            raise ValueError("Workflow 'steps' must be a list")

        # Validate each step has required fields
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(f"Step {i} must be a dictionary")

            required_fields = ["id", "tool"]
            for field in required_fields:
                if field not in step:
                    raise ValueError(f"Step {i} missing required field: {field}")

        logger.info("Parsed workflow with %s steps", len(steps))
        return steps

    except yaml.YAMLError as e:
        logger.error("YAML parsing error: %s", e)
        raise ValueError(f"Invalid YAML: {e}")


def resolve_template_variables(template_str: str, context: Dict[str, Any]) -> str:
    """
    Resolve template variables in a string.

    Supports simple {{ variable }} syntax.

    Args:
        template_str: String with template variables
        context: Dictionary of variable values

    Returns:
        String with variables resolved
    """
    if not isinstance(template_str, str):
        return template_str

    result = template_str

    # Simple template replacement for {{ cell.data.key }} patterns
    pattern = r"\{\{\s*(.+?)\s*\}\}"

    for match in re.finditer(pattern, template_str):
        var_path = match.group(1)

        # Navigate nested dict path (e.g., "cell.data.file_path")
        value = context
        for part in var_path.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                logger.warning("Template variable not found: %s", var_path)
                value = None
                break

        if value is not None:
            result = result.replace(match.group(0), str(value))

    return result


# ============================================================================
# LangGraph Nodes
# ============================================================================


def initialize_workflow(state: WorkflowState) -> WorkflowState:
    """
    Initialize workflow execution.

    This is the entry node of the LangGraph workflow.
    """
    logger.info("Initializing workflow for cell: %s", state['cell_id'])

    state["current_step_index"] = 0
    state["step_outputs"] = {}
    state["error"] = None
    state["completed"] = False

    return state


def execute_step(state: WorkflowState) -> WorkflowState:
    """
    Execute a single workflow step.

    This node handles executing one step at a time.
    """
    step_index = state["current_step_index"]
    steps = state["workflow_steps"]

    if step_index >= len(steps):
        logger.info("All workflow steps completed")
        state["completed"] = True
        return state

    step = steps[step_index]
    step_id = step["id"]

    logger.info("Executing step %s/%s: %s", step_index + 1, len(steps), step_id)

    try:
        # Get step configuration
        tool = step.get("tool")

        if tool == "run_script":
            # Execute script
            script_path = step.get("path")
            inputs = step.get("inputs", {})

            # Resolve template variables in inputs
            context = {
                "cell": {"id": state["cell_id"], "data": state["cell_data"]},
                "agent": state.get("agent_data", {}),
                "output": state["step_outputs"],
                "temp_dir": "/tmp",
            }

            resolved_inputs = {}
            for key, value in inputs.items():
                resolved_inputs[key] = resolve_template_variables(value, context)

            # Execute script
            result = run_script_tool(script_path, resolved_inputs)

            # Store outputs
            state["step_outputs"][step_id] = result

            if not result["success"]:
                state["error"] = f"Step '{step_id}' failed: {result['stderr']}"
                logger.error(state["error"])
                return state

            # Extract output path from stdout (last line)
            if result["stdout"]:
                output_lines = result["stdout"].strip().split("\n")
                if output_lines:
                    # Store the output path or result
                    outputs = step.get("outputs", {})
                    for output_key, output_template in outputs.items():
                        # For now, store the last line of stdout as output
                        state["step_outputs"][output_key] = output_lines[-1]

            logger.info("Step '%s' completed successfully", step_id)

        else:
            logger.warning("Unknown tool type: %s", tool)
            state["error"] = f"Unknown tool type: {tool}"
            return state

        # Move to next step
        state["current_step_index"] += 1

    except Exception as e:
        logger.error("Error executing step '%s': %s", step_id, e)
        state["error"] = str(e)

    return state


def should_continue(state: WorkflowState) -> str:
    """
    Decide whether to continue workflow or end.

    Returns:
        "execute_step" if more steps to execute
        "end" if workflow completed or error occurred
    """
    if state["error"]:
        return "end"

    if state["completed"]:
        return "end"

    if state["current_step_index"] < len(state["workflow_steps"]):
        return "execute_step"

    return "end"


def build_workflow_graph() -> StateGraph:
    """
    Build the LangGraph workflow execution graph.

    Returns:
        Compiled StateGraph for workflow execution
    """
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("initialize", initialize_workflow)
    workflow.add_node("execute_step", execute_step)

    # Add edges
    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "execute_step")
    workflow.add_conditional_edges(
        "execute_step", should_continue, {"execute_step": "execute_step", "end": END}
    )

    return workflow.compile()


# ============================================================================
# Custom Graph Loading
# ============================================================================


def load_custom_graph(graph_file_path: str):
    """
    Dynamically load and return a custom LangGraph from a Python file.

    This function enables the orchestrator to execute custom workflow graphs
    defined in Python files (e.g., ingestion_graph.py) instead of YAML workflows.

    Args:
        graph_file_path: Relative path to the graph Python file from BASE_DIR

    Returns:
        Compiled LangGraph workflow from the custom file

    Raises:
        FileNotFoundError: If the graph file doesn't exist
        AttributeError: If the graph file doesn't have a get_workflow_graph() function
        ImportError: If the module cannot be loaded (e.g., import errors)
        Exception: For other loading errors
    """
    try:
        # Resolve full path
        full_path = BASE_DIR / graph_file_path

        if not full_path.exists():
            raise FileNotFoundError(f"Graph file not found: {full_path}")

        logger.info("Loading custom graph from: %s", full_path)

        # Create a module spec from the file
        spec = importlib.util.spec_from_file_location("custom_graph", full_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to create module spec for: {full_path}")

        # Load the module
        module = importlib.util.module_from_spec(spec)
        sys.modules["custom_graph"] = module

        try:
            spec.loader.exec_module(module)
        except ImportError as ie:
            # Provide more context for import errors
            error_msg = (
                f"Import error while loading graph module '{graph_file_path}': {str(ie)}\n"
                f"Hint: Ensure all imports in the graph file use absolute imports "
                f"(e.g., 'from app.workflows.ingestion import ...' instead of 'from .ingestion import ...')"
            )
            logger.error(error_msg, exc_info=True)
            raise ImportError(error_msg) from ie

        # Get the workflow graph from the module
        if not hasattr(module, "get_workflow_graph"):
            raise AttributeError(
                f"Graph file {graph_file_path} must define a get_workflow_graph() function"
            )

        # Call the function to get the compiled graph
        graph = module.get_workflow_graph()

        logger.info("Successfully loaded custom graph from: %s", graph_file_path)
        return graph

    except (FileNotFoundError, ImportError, AttributeError):
        # Re-raise these specific exceptions with their enhanced messages
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        logger.error("Unexpected error loading custom graph from %s: %s", graph_file_path, e, exc_info=True)
        raise


def find_graph_reference(cell_type: "NotebookItemType") -> Optional[str]:
    """
    Search for a workflow graph reference in cell type's default_refs['workflow_graph'].

    Args:
        cell_type: NotebookItemType instance to search

    Returns:
        Path to the graph file if found, None otherwise
    """
    # Get workflow_graph references from default_refs dictionary
    workflow_refs = cell_type.default_refs.get("workflow_graph", [])

    if not workflow_refs:
        return None

    for workflow_ref in workflow_refs:
        if workflow_ref.endswith("graph.py"):
            logger.info("Found graph reference: %s", workflow_ref)
            return workflow_ref

    return None
