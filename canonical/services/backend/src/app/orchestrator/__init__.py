"""
Orchestrator Module

This module provides the orchestrator functionality for the ScareVerse workflow system.
The orchestrator manages cell workflow execution using LangGraph.

Structure:
- state.py: State definitions
- file_processing.py: File handling logic
- core.py: Orchestrator class with workflow execution logic
- helpers.py: Helper functions for conversion and Redis publishing
- instance.py: Global instance management and entry point

Public API:
- Orchestrator: Main orchestrator class
- set_orchestrator_instance: Set global orchestrator instance
- get_orchestrator_instance: Get global orchestrator instance
- Helper functions for cell conversion and Redis publishing
- State and file processing utilities
"""

from .core import Orchestrator
from .file_processing import (
    get_file_ids_for_llm,
    get_segmented_content_for_ollama,
    process_attached_files,
)
from .helpers import (
    cell_to_pipeline_item,
    publish_fragment_to_redis,
    publish_pipeline_fragments,
    set_redis_client,
    update_cell_from_pipeline_item,
)
from .instance import get_orchestrator_instance, main, set_orchestrator_instance
from .state import OrchestratorState

__all__ = [
    # Core orchestrator
    "Orchestrator",
    "set_orchestrator_instance",
    "get_orchestrator_instance",
    "main",
    # State management
    "OrchestratorState",
    # File processing
    "process_attached_files",
    "get_segmented_content_for_ollama",
    "get_file_ids_for_llm",
    # Helper functions
    "cell_to_pipeline_item",
    "update_cell_from_pipeline_item",
    "publish_fragment_to_redis",
    "publish_pipeline_fragments",
    "set_redis_client",
]
