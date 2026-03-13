---
processed: true
processed_date: 2025-12-08
themes:
  - mcp
  - integration
  - tools
  - api
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# MCP Server Integration Guide

This guide explains how to integrate the MCP server with the existing ScareVerse infrastructure, particularly with the LangGraph chat orchestrator.

## Quick Start

### 1. Basic Server Setup

```python
from app.mcp import MCPServer, MCPConfig

# Create server with configuration
config = MCPConfig(
    enable_file_tools=True,
    enable_cell_tools=True,
    enable_repo_tools=True
)

server = MCPServer(config)
await server.initialize()
```

### 2. Using Tools

```python
# Execute a tool
result = await server.execute_tool("list_directory", {
    "path": ".",
    "include_hidden": False
})

if result["success"]:
    print(f"Found {result['result']['count']} items")
else:
    print(f"Error: {result['error']}")
```

## Integration with LangGraph Chat Orchestrator

### Option 1: Direct Integration in Orchestrator Nodes

Modify the existing `langgraph_chat_flow.py` to include MCP tools:

```python
from app.mcp import get_mcp_server

# In ChatOrchestrator.__init__
async def __init__(self):
    self.mcp_server = get_mcp_server()
    await self.mcp_server.initialize()
    # ... rest of initialization

# Create new node for MCP tool execution
async def _execute_mcp_tool(self, state: OrchestratorState) -> OrchestratorState:
    """Execute MCP tool based on user request."""
    tool_name = state.get("mcp_tool_name")
    tool_params = state.get("mcp_tool_params", {})
    
    if tool_name:
        result = await self.mcp_server.execute_tool(tool_name, tool_params)
        state["mcp_result"] = result
    
    return state
```

### Option 2: MCP Router Endpoint

Create a new FastAPI endpoint for MCP tools:

```python
# In backend/app/routers/mcp_router.py
from fastapi import APIRouter, HTTPException
from app.mcp import get_mcp_server

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

@router.post("/execute")
async def execute_mcp_tool(
    tool_name: str,
    params: dict
):
    """Execute an MCP tool."""
    server = get_mcp_server()
    result = await server.execute_tool(tool_name, params)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@router.get("/tools")
async def list_mcp_tools(category: str = None):
    """List available MCP tools."""
    server = get_mcp_server()
    return server.list_tools(category=category)
```

### Option 3: LangChain Tool Wrapper

Convert MCP tools to LangChain tools for seamless integration:

```python
from langchain_core.tools import BaseTool
from app.mcp import get_mcp_server

class MCPLangChainTool(BaseTool):
    """LangChain wrapper for MCP tool."""
    
    mcp_tool_name: str
    
    async def _arun(self, **kwargs):
        server = get_mcp_server()
        result = await server.execute_tool(self.mcp_tool_name, kwargs)
        
        if not result["success"]:
            raise ValueError(result["error"])
        
        return result["result"]

# Create LangChain tools from MCP
async def create_langchain_tools():
    server = get_mcp_server()
    await server.initialize()
    
    tools = []
    for tool_name in server.tools.keys():
        tool = server.get_tool(tool_name)
        lc_tool = MCPLangChainTool(
            name=tool.name,
            description=tool.description,
            mcp_tool_name=tool.name
        )
        tools.append(lc_tool)
    
    return tools
```

## Integration with OrchestratorState

Add MCP-specific fields to `langgraph_state.py`:

```python
class OrchestratorState(TypedDict):
    # ... existing fields
    
    # MCP integration fields
    mcp_tool_name: Optional[str]  # MCP tool to execute
    mcp_tool_params: Optional[Dict[str, Any]]  # Parameters for MCP tool
    mcp_result: Optional[Dict[str, Any]]  # Result from MCP tool execution
    enable_mcp: bool  # Whether to use MCP tools for this request
```

## Usage Examples

### File System Operations

```python
# List directory
result = await server.execute_tool("list_directory", {
    "path": "backend/app",
    "include_hidden": False,
    "recursive": False
})

# Read file
result = await server.execute_tool("read_file", {
    "path": "backend/app/mcp/README.md",
    "encoding": "utf-8"
})

# Write file
result = await server.execute_tool("write_file", {
    "path": "output/test.txt",
    "content": "Hello from MCP!",
    "create_dirs": True
})

# Search files
result = await server.execute_tool("search_files", {
    "pattern": "*.py",
    "path": "backend/app/mcp",
    "recursive": True
})
```

### Cell Management

```python
# Create cell
result = await server.execute_tool("create_cell", {
    "assignee_id": "user123",
    "cell_type_id": "cell_type_001",
    "initial_data": {"key": "value"}
})

# List cells
result = await server.execute_tool("list_cells", {
    "assignee_id": "user123",
    "state": "active",
    "limit": 10
})

# Get cell
result = await server.execute_tool("get_cell", {
    "cell_id": "cell_001"
})
```

### Repository Navigation

```python
# Search code
result = await server.execute_tool("search_code", {
    "query": "MCPServer",
    "path": "backend/app",
    "file_pattern": "*.py",
    "max_results": 50
})

# Get project structure
result = await server.execute_tool("get_project_structure", {
    "path": "backend/app/mcp",
    "max_depth": 2
})

# Get file info
result = await server.execute_tool("get_file_info", {
    "path": "backend/app/mcp/server.py"
})
```

## Environment Configuration

Add MCP-specific environment variables to `.env`:

```bash
# MCP Server Configuration
MCP_SERVER_NAME=scareverse-mcp
MCP_MAX_CONCURRENT=10
MCP_TIMEOUT_SECONDS=30
MCP_ENABLE_LOGGING=true
MCP_SANDBOX_FILES=true
```

## Security Considerations

The MCP server implements several security measures:

1. **Path Sandboxing**: All file operations are restricted to the project directory
2. **File Size Limits**: Maximum file size for read/write operations (configurable)
3. **Timeout Protection**: Tool execution timeouts to prevent hanging
4. **Concurrency Control**: Maximum concurrent requests limit
5. **Input Validation**: Parameter validation for all tools

## Testing

Run the MCP test suite:

```bash
cd backend
pytest tests/unit/mcp/ -v
```

Run the example script:

```bash
cd backend
python -m app.mcp.example_usage
```

## Troubleshooting

### Import Errors

If you get import errors, ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

### Database Connection Errors

Cell tools require database connection. If testing without a database:
- Mock the database layer
- Skip cell-related tests
- Use file tools and repo tools instead

### Performance Issues

If experiencing slow tool execution:
- Increase `MCP_MAX_CONCURRENT` for more parallel requests
- Reduce `MCP_TIMEOUT_SECONDS` to fail faster
- Profile specific tool implementations

## Next Steps

1. **Integration with Chat UI**: Expose MCP tools through chat interface
2. **Dynamic View Generation**: Implement view generation tools
3. **Issue Pipeline**: Complete issue automation tools
4. **Custom Tools**: Add project-specific tools as needed

## References

- [MCP Server README](./README.md)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [ScareVerse Architecture](../../../docs/concept/architecture.md)

---

**Last Updated**: November 2025  
**Maintained By**: Middleware Agent
