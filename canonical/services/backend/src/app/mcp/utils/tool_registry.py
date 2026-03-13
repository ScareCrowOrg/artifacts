"""
Tool Registry Utilities

Helper functions for managing MCP tool registration and discovery.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for organizing and discovering MCP tools.
    """

    def __init__(self):
        """Initialize the tool registry."""
        self.tools_by_category: Dict[str, List[str]] = {}
        self.tool_metadata: Dict[str, Dict[str, Any]] = {}

    def register_tool_metadata(
        self, tool_name: str, category: str, metadata: Dict[str, Any]
    ) -> None:
        """
        Register metadata for a tool.

        Args:
            tool_name: Tool name
            category: Tool category
            metadata: Additional metadata
        """
        if category not in self.tools_by_category:
            self.tools_by_category[category] = []

        if tool_name not in self.tools_by_category[category]:
            self.tools_by_category[category].append(tool_name)

        self.tool_metadata[tool_name] = {**metadata, "category": category}

    def get_tools_by_category(self, category: str) -> List[str]:
        """
        Get all tools in a category.

        Args:
            category: Category name

        Returns:
            List of tool names
        """
        return self.tools_by_category.get(category, [])

    def get_tool_metadata(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a tool.

        Args:
            tool_name: Tool name

        Returns:
            Tool metadata or None
        """
        return self.tool_metadata.get(tool_name)

    def list_categories(self) -> List[str]:
        """
        List all registered categories.

        Returns:
            List of category names
        """
        return list(self.tools_by_category.keys())

    def search_tools(self, query: str) -> List[str]:
        """
        Search for tools by name or description.

        Args:
            query: Search query

        Returns:
            List of matching tool names
        """
        query_lower = query.lower()
        matches = []

        for tool_name, metadata in self.tool_metadata.items():
            if query_lower in tool_name.lower():
                matches.append(tool_name)
            elif query_lower in metadata.get("description", "").lower():
                matches.append(tool_name)

        return matches


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """
    Get the global tool registry.

    Returns:
        ToolRegistry instance
    """
    return _registry
