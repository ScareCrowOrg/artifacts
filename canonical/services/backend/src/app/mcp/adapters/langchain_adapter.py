"""
LangChain to MCP Adapter

Adapts existing LangChain tools to work with the MCP server.
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict

from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from ..server import MCPServer

logger = logging.getLogger(__name__)


class LangChainMCPAdapter:
    """Adapter to convert LangChain tools to MCP tools."""

    def __init__(self):
        """Initialize the adapter."""
        self.converted_tools = {}

    @staticmethod
    def langchain_tool_to_mcp_handler(tool: BaseTool) -> Callable:
        """
        Convert a LangChain tool to an MCP handler function.

        Args:
            tool: LangChain BaseTool instance

        Returns:
            Async handler function for MCP
        """

        async def mcp_handler(params: Dict[str, Any]) -> Dict[str, Any]:
            """MCP handler wrapping LangChain tool."""
            try:
                # Execute LangChain tool
                if hasattr(tool, "ainvoke"):
                    result = await tool.ainvoke(params)
                elif hasattr(tool, "arun"):
                    result = await tool.arun(**params)
                else:
                    # Sync tool fallback
                    result = tool.invoke(params)

                return {"success": True, "result": result}

            except Exception as e:
                logger.error("Error executing LangChain tool %s: %s", tool.name, e)
                return {"success": False, "error": str(e)}

        return mcp_handler

    def convert_tool(self, tool: BaseTool) -> Dict[str, Any]:
        """
        Convert a LangChain tool to MCP format.

        Args:
            tool: LangChain BaseTool instance

        Returns:
            Dictionary with MCP tool configuration
        """
        # Extract parameters from LangChain tool schema
        parameters = {}

        if hasattr(tool, "args_schema") and tool.args_schema:
            # Parse Pydantic schema
            schema = tool.args_schema.schema()
            properties = schema.get("properties", {})

            for prop_name, prop_schema in properties.items():
                parameters[prop_name] = {
                    "type": prop_schema.get("type", "string"),
                    "description": prop_schema.get("description", ""),
                }

        return {
            "name": tool.name,
            "description": tool.description or f"LangChain tool: {tool.name}",
            "parameters": parameters,
            "handler": self.langchain_tool_to_mcp_handler(tool),
        }

    def register_langchain_tool(
        self, server: "MCPServer", tool: BaseTool, category: str = "langchain"
    ) -> None:
        """
        Register a LangChain tool with the MCP server.

        Args:
            server: MCPServer instance
            tool: LangChain BaseTool to register
            category: Tool category
        """
        try:
            mcp_tool_config = self.convert_tool(tool)

            server.register_tool(
                name=mcp_tool_config["name"],
                description=mcp_tool_config["description"],
                parameters=mcp_tool_config["parameters"],
                handler=mcp_tool_config["handler"],
                category=category,
            )

            self.converted_tools[tool.name] = tool

            logger.info("Registered LangChain tool %s with MCP server", tool.name)

        except Exception as e:
            logger.error("Error registering LangChain tool %s: %s", tool.name, e)
            raise


def initialize(_server: "MCPServer") -> None:
    """
    Initialize LangChain adapter and register existing tools.

    Args:
        server: MCPServer instance
    """
    try:
        _adapter = LangChainMCPAdapter()

        # Try to import and register existing LangChain tools
        try:
            from ...langchain_tools import CellTools

            # Create tool instances from CellTools methods if needed
            # For now, we're using the direct MCP implementation in cell_tools.py
            logger.info("LangChain CellTools available for MCP integration")

        except ImportError:
            logger.warning("LangChain tools not available for integration")

        logger.info("LangChain adapter initialized")

    except Exception as e:
        logger.error("Error initializing LangChain adapter: %s", e)
        raise
