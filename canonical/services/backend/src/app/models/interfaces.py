"""
Interfaces for notebook item execution.

This module defines abstract contracts for pipeline execution,
enabling the Adapter pattern for flexible execution of notebook items.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IPipelineExecutable(ABC):
    """
    Interface for items that can be executed in a pipeline.

    This interface defines the contract that any executable notebook item
    must implement. It enables the workflow executor to work with any
    type of notebook item (cells, books, etc.) in a uniform way.

    The interface follows the Adapter pattern, allowing pure data models
    to remain focused on data representation while execution logic is
    handled by adapter implementations.
    """

    @abstractmethod
    async def execute_in_pipeline(self, pipeline_item_instance: "PipelineItem") -> Any:
        """
        Execute the notebook item within a pipeline context.

        This method is called by the workflow executor to perform the actual
        execution of the notebook item. The pipeline_item_instance provides
        the execution context and state management.

        Args:
            pipeline_item_instance: The PipelineItem instance managing execution state

        Returns:
            Result of the execution (type depends on implementation)

        Raises:
            Exception: If execution fails
        """

    @abstractmethod
    def get_references(self) -> Dict[str, List[str]]:
        """
        Get file references for this notebook item.

        Returns a dictionary mapping reference types to lists of file paths/IDs.
        Example: {
            "docs": ["path/to/doc.md"],
            "python": ["path/to/script.py"],
            "yaml": ["path/to/config.yaml"]
        }

        Returns:
            Dictionary of reference type to file paths
        """

    @abstractmethod
    def get_pipeline_context_name(self) -> str:
        """
        Get the context name for pipeline execution.

        This name is used by the workflow executor to identify the type
        of execution context (e.g., "cell_execution", "book_orchestration").

        Returns:
            String identifying the pipeline context
        """
