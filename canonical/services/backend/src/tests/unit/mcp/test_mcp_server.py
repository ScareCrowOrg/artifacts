"""
Unit Tests for MCP Server Core

Tests for the MCP server initialization, tool registration, and execution.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.mcp import MCPServer, MCPConfig


@pytest.fixture
def mcp_config():
    """Create test MCP configuration."""
    return MCPConfig(
        server_name="test-mcp",
        version="1.0.0-test",
        max_concurrent_requests=5,
        timeout_seconds=10,
        enable_logging=False
    )


@pytest.fixture
def mcp_server(mcp_config):
    """Create test MCP server instance."""
    return MCPServer(config=mcp_config)


class TestMCPServer:
    """Test cases for MCPServer class."""
    
    def test_server_initialization(self, mcp_server, mcp_config):
        """Test that server initializes correctly."""
        assert mcp_server.config == mcp_config
        assert len(mcp_server.tools) == 0
        assert len(mcp_server.tool_categories) == 0
    
    def test_get_server_info(self, mcp_server):
        """Test server info retrieval."""
        info = mcp_server.get_server_info()
        
        assert info["name"] == "test-mcp"
        assert info["version"] == "1.0.0-test"
        assert info["tool_count"] == 0
        assert "capabilities" in info
    
    @pytest.mark.asyncio
    async def test_register_tool(self, mcp_server):
        """Test tool registration."""
        # Create a mock handler
        async def mock_handler(params):
            return {"result": "test"}
        
        # Register tool
        mcp_server.register_tool(
            name="test_tool",
            description="A test tool",
            parameters={"param1": {"type": "string"}},
            handler=mock_handler,
            category="test"
        )
        
        # Verify registration
        assert "test_tool" in mcp_server.tools
        assert "test" in mcp_server.tool_categories
        assert "test_tool" in mcp_server.tool_categories["test"]
    
    def test_get_tool(self, mcp_server):
        """Test tool retrieval."""
        # Create and register a tool
        async def mock_handler(params):
            return {"result": "test"}
        
        mcp_server.register_tool(
            name="test_tool",
            description="A test tool",
            parameters={},
            handler=mock_handler
        )
        
        # Retrieve tool
        tool = mcp_server.get_tool("test_tool")
        
        assert tool is not None
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
    
    def test_get_nonexistent_tool(self, mcp_server):
        """Test retrieval of non-existent tool."""
        tool = mcp_server.get_tool("nonexistent_tool")
        assert tool is None
    
    def test_list_tools(self, mcp_server):
        """Test listing all tools."""
        # Register multiple tools
        async def mock_handler(params):
            return {"result": "test"}
        
        mcp_server.register_tool(
            name="tool1",
            description="Tool 1",
            parameters={},
            handler=mock_handler,
            category="cat1"
        )
        
        mcp_server.register_tool(
            name="tool2",
            description="Tool 2",
            parameters={},
            handler=mock_handler,
            category="cat2"
        )
        
        # List all tools
        tools = mcp_server.list_tools()
        assert len(tools) == 2
        
        # List tools by category
        cat1_tools = mcp_server.list_tools(category="cat1")
        assert len(cat1_tools) == 1
        assert cat1_tools[0]["name"] == "tool1"
    
    @pytest.mark.asyncio
    async def test_execute_tool_success(self, mcp_server):
        """Test successful tool execution."""
        # Create a mock handler
        async def mock_handler(params):
            return {"data": params.get("input", "default")}
        
        # Register tool
        mcp_server.register_tool(
            name="test_tool",
            description="Test tool",
            parameters={"input": {"type": "string"}},
            handler=mock_handler
        )
        
        # Execute tool
        result = await mcp_server.execute_tool(
            "test_tool",
            {"input": "test_value"}
        )
        
        assert result["success"] is True
        assert result["result"]["data"] == "test_value"
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, mcp_server):
        """Test execution of non-existent tool."""
        result = await mcp_server.execute_tool(
            "nonexistent_tool",
            {}
        )
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_tool_error(self, mcp_server):
        """Test tool execution with error."""
        # Create a handler that raises an error
        async def error_handler(params):
            raise ValueError("Test error")
        
        # Register tool
        mcp_server.register_tool(
            name="error_tool",
            description="Error tool",
            parameters={},
            handler=error_handler
        )
        
        # Execute tool
        result = await mcp_server.execute_tool("error_tool", {})
        
        assert result["success"] is False
        assert "Test error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_timeout(self, mcp_server):
        """Test tool execution timeout."""
        # Create a slow handler
        import asyncio
        
        async def slow_handler(params):
            await asyncio.sleep(20)  # Exceeds timeout
            return {"result": "too slow"}
        
        # Register tool
        mcp_server.register_tool(
            name="slow_tool",
            description="Slow tool",
            parameters={},
            handler=slow_handler
        )
        
        # Execute tool (should timeout)
        result = await mcp_server.execute_tool("slow_tool", {})
        
        assert result["success"] is False
        assert "timed out" in result["error"].lower()
    
    def test_tool_to_schema(self, mcp_server):
        """Test tool schema conversion."""
        async def mock_handler(params):
            return {}
        
        # Register tool
        mcp_server.register_tool(
            name="schema_tool",
            description="Tool for schema test",
            parameters={
                "param1": {"type": "string", "description": "First param"},
                "param2": {"type": "integer", "description": "Second param"}
            },
            handler=mock_handler
        )
        
        # Get tool and convert to schema
        tool = mcp_server.get_tool("schema_tool")
        schema = tool.to_schema()
        
        assert schema["name"] == "schema_tool"
        assert schema["description"] == "Tool for schema test"
        assert "inputSchema" in schema
        assert "properties" in schema["inputSchema"]
        assert "param1" in schema["inputSchema"]["properties"]


class TestMCPConfig:
    """Test cases for MCPConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = MCPConfig()
        
        assert config.server_name == "scareverse-mcp"
        assert config.version == "1.0.0"
        assert config.max_concurrent_requests == 10
        assert config.timeout_seconds == 30
        assert config.enable_logging is True
        assert config.sandbox_file_operations is True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = MCPConfig(
            server_name="custom-mcp",
            version="2.0.0",
            max_concurrent_requests=20,
            enable_logging=False
        )
        
        assert config.server_name == "custom-mcp"
        assert config.version == "2.0.0"
        assert config.max_concurrent_requests == 20
        assert config.enable_logging is False
    
    @patch.dict('os.environ', {
        'MCP_SERVER_NAME': 'env-mcp',
        'MCP_MAX_CONCURRENT': '15',
        'MCP_TIMEOUT_SECONDS': '60'
    })
    def test_config_from_env(self):
        """Test configuration from environment variables."""
        config = MCPConfig.from_env()
        
        assert config.server_name == "env-mcp"
        assert config.max_concurrent_requests == 15
        assert config.timeout_seconds == 60
    
    def test_config_to_dict(self):
        """Test configuration to dictionary conversion."""
        config = MCPConfig(server_name="test-mcp")
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict["server_name"] == "test-mcp"
        assert "max_concurrent_requests" in config_dict
