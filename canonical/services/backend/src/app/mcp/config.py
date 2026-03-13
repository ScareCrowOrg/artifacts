"""
MCP Configuration

Centralized configuration for the Model Context Protocol server.
"""

import os
from typing import Any, Dict

from pydantic import BaseModel, Field


class MCPConfig(BaseModel):
    """Configuration for MCP server."""

    # Server identification
    server_name: str = Field(
        default="scareverse-mcp", description="Name of the MCP server"
    )

    version: str = Field(default="1.0.0", description="MCP server version")

    # Performance settings
    max_concurrent_requests: int = Field(
        default=10, description="Maximum number of concurrent tool requests"
    )

    timeout_seconds: int = Field(
        default=30, description="Default timeout for tool execution"
    )

    # Feature flags
    enable_logging: bool = Field(
        default=True, description="Enable detailed logging of MCP operations"
    )

    enable_file_tools: bool = Field(
        default=True, description="Enable file system tools"
    )

    enable_cell_tools: bool = Field(
        default=True, description="Enable cell/book management tools"
    )

    enable_repo_tools: bool = Field(
        default=True, description="Enable repository navigation tools"
    )

    enable_issue_tools: bool = Field(
        default=False, description="Enable issue pipeline tools (experimental)"
    )

    # Security settings
    sandbox_file_operations: bool = Field(
        default=True, description="Restrict file operations to project directory"
    )

    max_file_size_mb: int = Field(
        default=10, description="Maximum file size for read/write operations (MB)"
    )

    # Integration settings
    langchain_integration: bool = Field(
        default=True, description="Enable LangChain tool adapter"
    )

    langgraph_integration: bool = Field(
        default=True, description="Enable LangGraph workflow integration"
    )

    @classmethod
    def from_env(cls) -> "MCPConfig":
        """
        Create configuration from environment variables.

        Returns:
            MCPConfig instance with values from environment
        """
        return cls(
            server_name=os.getenv("MCP_SERVER_NAME", "scareverse-mcp"),
            max_concurrent_requests=int(os.getenv("MCP_MAX_CONCURRENT", "10")),
            timeout_seconds=int(os.getenv("MCP_TIMEOUT_SECONDS", "30")),
            enable_logging=os.getenv("MCP_ENABLE_LOGGING", "true").lower() == "true",
            sandbox_file_operations=os.getenv("MCP_SANDBOX_FILES", "true").lower()
            == "true",
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary representation of config
        """
        return self.model_dump()


# Default configuration instance
default_config = MCPConfig()
