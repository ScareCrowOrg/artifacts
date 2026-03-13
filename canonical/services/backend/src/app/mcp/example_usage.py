"""
MCP Server Usage Example

This script demonstrates how to initialize and use the MCP server.
"""

import asyncio
import logging

from app.mcp import MCPConfig, MCPServer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main example function."""

    # Create MCP server with custom configuration
    config = MCPConfig(
        server_name="scareverse-mcp-example",
        enable_logging=True,
        enable_file_tools=True,
        enable_cell_tools=True,
        enable_repo_tools=True,
    )

    server = MCPServer(config)

    # Initialize server (loads all enabled tools)
    logger.info("Initializing MCP server...")
    await server.initialize()

    # Get server info
    info = server.get_server_info()
    logger.info("Server initialized: %s v%s", info['name'], info['version'])
    logger.info("Tools loaded: %s", info['tool_count'])
    logger.info("Categories: %s", ', '.join(info['categories']))

    # List all available tools
    logger.info("\nAvailable tools:")
    for category in info["categories"]:
        tools = server.list_tools(category=category)
        logger.info("\n%s (%s tools):", category.upper(), len(tools))
        for tool in tools:
            logger.info("  - %s: %s", tool['name'], tool['description'])

    # Example 1: List directory
    logger.info("\n=== Example 1: List Directory ===")
    result = await server.execute_tool(
        "list_directory", {"path": ".", "include_hidden": False}
    )

    if result["success"]:
        logger.info("Found %s items", result['result']['count'])
        for item in result["result"]["items"][:5]:  # Show first 5
            logger.info("  - %s (%s)", item['name'], item['type'])
    else:
        logger.error("Error: %s", result['error'])

    # Example 2: Search for Python files
    logger.info("\n=== Example 2: Search for Python Files ===")
    result = await server.execute_tool(
        "search_files", {"pattern": "*.py", "path": "app/mcp", "recursive": True}
    )

    if result["success"]:
        logger.info("Found %s Python files", result['result']['count'])
        for match in result["result"]["matches"][:5]:  # Show first 5
            logger.info("  - %s", match['path'])
    else:
        logger.error("Error: %s", result['error'])

    # Example 3: Get file info
    logger.info("\n=== Example 3: Get File Info ===")
    result = await server.execute_tool("get_file_info", {"path": "app/mcp/README.md"})

    if result["success"]:
        info = result["result"]
        logger.info("File: %s", info['name'])
        logger.info("Size: %s bytes", info['size'])
        logger.info("Lines: %s", info.get('lines', 'N/A'))
    else:
        logger.error("Error: %s", result['error'])

    # Example 4: Create cell (if database is available)
    logger.info("\n=== Example 4: Create Cell (Example) ===")
    # Note: This will fail if database is not initialized
    # Uncomment to test with a valid database
    """
    result = await server.execute_tool("create_cell", {
        "assignee_id": "test_user",
        "title": "Example Cell"
    })

    if result["success"]:
        logger.info("Cell created: %s", result['result']['celula_id'])
    else:
        logger.info("Cell creation skipped (database not available): %s", result['error'])
    """
    logger.info("Cell creation example skipped (requires database)")

    logger.info("\n=== MCP Server Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
