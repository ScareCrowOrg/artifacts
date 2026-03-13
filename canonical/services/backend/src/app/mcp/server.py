"""
MCP Server Implementation

Core MCP server that handles tool registration, routing, and execution.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .config import MCPConfig, default_config

logger = logging.getLogger(__name__)


class MCPTool:
    """Base class for MCP tools."""

    def __init__(
        self, name: str, description: str, parameters: Dict[str, Any], handler: Callable
    ):
        """
        Initialize MCP tool.

        Args:
            name: Tool name
            description: Tool description
            parameters: JSON schema for tool parameters
            handler: Async function to execute the tool
        """
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool with given arguments.

        Args:
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        try:
            result = await self.handler(arguments)
            return {
                "success": True,
                "result": result,
                "tool": self.name,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error("Error executing tool %s: %s", self.name, e)
            return {
                "success": False,
                "error": str(e),
                "tool": self.name,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def to_schema(self) -> Dict[str, Any]:
        """
        Convert tool to MCP schema format.

        Returns:
            Tool schema dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.parameters,
                "required": list(self.parameters.keys()),
            },
        }


class MCPServer:
    """
    Model Context Protocol Server.

    Manages tool registration, routing, and execution for AI assistants.
    """

    def __init__(self, config: Optional[MCPConfig] = None):
        """
        Initialize MCP server.

        Args:
            config: Server configuration (uses default if not provided)
        """
        self.config = config or default_config
        self.tools: Dict[str, MCPTool] = {}
        self.tool_categories: Dict[str, List[str]] = {}
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

        if self.config.enable_logging:
            logger.setLevel(logging.INFO)

        logger.info("Initializing MCP Server: %s v%s", self.config.server_name, self.config.version)

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        category: Optional[str] = None,
    ) -> None:
        """
        Register a new tool with the MCP server.

        Args:
            name: Tool name (must be unique)
            description: Tool description
            parameters: JSON schema for parameters
            handler: Async function to handle tool execution
            category: Optional category for organization
        """
        if name in self.tools:
            logger.warning("Tool %s already registered, overwriting", name)

        tool = MCPTool(name, description, parameters, handler)
        self.tools[name] = tool

        if category:
            if category not in self.tool_categories:
                self.tool_categories[category] = []
            self.tool_categories[category].append(name)

        logger.info("Registered tool: %s (category: %s)", name, category or 'default')

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """
        Get a registered tool by name.

        Args:
            name: Tool name

        Returns:
            MCPTool instance or None if not found
        """
        return self.tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all registered tools or tools in a specific category.

        Args:
            category: Optional category filter

        Returns:
            List of tool schemas
        """
        if category and category in self.tool_categories:
            tool_names = self.tool_categories[category]
            tools = [self.tools[name] for name in tool_names]
        else:
            tools = list(self.tools.values())

        return [tool.to_schema() for tool in tools]

    async def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a registered tool with concurrency control.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        tool = self.get_tool(tool_name)

        if not tool:
            return {
                "success": False,
                "error": f"Tool not found: {tool_name}",
                "timestamp": datetime.utcnow().isoformat(),
            }

        async with self._semaphore:
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    tool.execute(arguments), timeout=self.config.timeout_seconds
                )
                return result
            except asyncio.TimeoutError:
                logger.error("Tool %s execution timed out", tool_name)
                return {
                    "success": False,
                    "error": f"Tool execution timed out after {self.config.timeout_seconds}s",
                    "tool": tool_name,
                    "timestamp": datetime.utcnow().isoformat(),
                }

    def register_tool_category(self, category: str, tools: List[str]) -> None:
        """
        Register a category of related tools.

        Args:
            category: Category name
            tools: List of tool names in this category
        """
        self.tool_categories[category] = tools
        logger.info("Registered tool category: %s (%s tools)", category, len(tools))

    async def initialize(self) -> None:
        """
        Initialize the MCP server and load tools.

        This method loads and registers all enabled tool categories.
        """
        logger.info("Initializing MCP Server tools...")

        # Import and register tool modules based on configuration
        if self.config.enable_file_tools:
            from .tools import file_tools

            file_tools.register(self)
            logger.info("File tools registered")

        if self.config.enable_cell_tools:
            from .tools import cell_tools

            cell_tools.register(self)
            logger.info("Cell tools registered")

        if self.config.enable_repo_tools:
            from .tools import repo_tools

            repo_tools.register(self)
            logger.info("Repository tools registered")

        if self.config.enable_issue_tools:
            from .tools import issue_tools

            issue_tools.register(self)
            logger.info("Issue tools registered")

        # Initialize LangChain adapter if enabled
        if self.config.langchain_integration:
            from .adapters import langchain_adapter

            langchain_adapter.initialize(self)
            logger.info("LangChain adapter initialized")

        logger.info("MCP Server initialized with %s tools in %s categories", len(self.tools), len(self.tool_categories))

    def get_server_info(self) -> Dict[str, Any]:
        """
        Get server information and capabilities.

        Returns:
            Server info dictionary
        """
        return {
            "name": self.config.server_name,
            "version": self.config.version,
            "capabilities": {
                "tools": True,
                "logging": self.config.enable_logging,
            },
            "tool_count": len(self.tools),
            "categories": list(self.tool_categories.keys()),
        }


# Global server instance
_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """
    Get or create the global MCP server instance.

    Returns:
        MCPServer instance
    """
    global _mcp_server

    if _mcp_server is None:
        _mcp_server = MCPServer()

    return _mcp_server
