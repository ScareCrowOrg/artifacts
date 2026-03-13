"""
Cell and Book Management Tools for MCP

Tools for creating and managing cells and books (notebooks) in ScareVerse.
Integrates with existing LangChain cell tools.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..server import MCPServer

logger = logging.getLogger(__name__)


async def create_cell(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new cell in ScareVerse.

    Args:
        params: {
            "assignee_id": str - User ID responsible for the cell
            "cell_type_id": str - Optional cell type ID
            "initial_data": dict - Optional initial data
            "title": str - Optional cell title
        }

    Returns:
        Dictionary with created cell information
    """
    try:
        # Import LangChain cell tools
        # Note: Requires existing langchain_tools module from ScareVerse
        from ...langchain_tools import CellTools

        assignee_id = params["assignee_id"]
        cell_type_id = params.get("cell_type_id")
        initial_data = params.get("initial_data")

        # Use existing LangChain cell creation logic
        result = await CellTools.criar_celula_impl(
            responsavel_id=assignee_id,
            tipo_celula_id=cell_type_id,
            dados_iniciais=initial_data,
        )

        if result.get("success"):
            logger.info("Cell created via MCP: %s", result.get('celula_id'))

        return result

    except ImportError as e:
        logger.error("LangChain tools not available: %s", e)
        return {
            "success": False,
            "error": "Cell creation requires langchain_tools module",
        }
    except Exception as e:
        logger.error("Error creating cell via MCP: %s", e)
        raise


async def execute_cell(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute an existing cell.

    Args:
        params: {
            "cell_id": str - Cell ID to execute
            "execution_params": dict - Optional execution parameters
        }

    Returns:
        Dictionary with execution result
    """
    try:
        # Import LangChain cell tools
        # Note: Requires existing langchain_tools module from ScareVerse
        from ...langchain_tools import CellTools

        cell_id = params["cell_id"]
        execution_params = params.get("execution_params", {})

        # Use existing LangChain cell execution logic
        result = await CellTools.executar_celula_impl(
            celula_id=cell_id, dados_execucao=execution_params
        )

        if result.get("success"):
            logger.info("Cell executed via MCP: %s", cell_id)

        return result

    except ImportError as e:
        logger.error("LangChain tools not available: %s", e)
        return {
            "success": False,
            "error": "Cell execution requires langchain_tools module",
        }
    except Exception as e:
        logger.error("Error executing cell via MCP: %s", e)
        raise


async def get_cell(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get cell information.

    Args:
        params: {
            "cell_id": str - Cell ID to retrieve
        }

    Returns:
        Dictionary with cell information
    """
    try:
        from ...database import db
        from ...models import Cell

        cell_id = params["cell_id"]

        # Fetch cell from database
        cell = db.find_one("cells", cell_id, Cell, is_canonical=False)

        if not cell:
            return {"success": False, "error": f"Cell not found: {cell_id}"}

        return {
            "success": True,
            "cell": {
                "id": cell.id,
                "assignee_id": cell.assignee_id,
                "cell_type_id": cell.notebook_item_type_id,
                "state": cell.status.value,
                "created_at": cell.created_at.isoformat() if cell.created_at else None,
                "fragments_count": len(cell.fragments),
            },
        }

    except Exception as e:
        logger.error("Error getting cell via MCP: %s", e)
        raise


async def list_cells(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    List cells with optional filtering.

    Args:
        params: {
            "assignee_id": str - Optional filter by assignee
            "cell_type_id": str - Optional filter by cell type
            "state": str - Optional filter by state
            "limit": int - Max results (default: 50)
        }

    Returns:
        Dictionary with list of cells
    """
    try:
        from ...database import db
        from ...models import Cell

        assignee_id = params.get("assignee_id")
        cell_type_id = params.get("cell_type_id")
        state = params.get("state")
        limit = params.get("limit", 50)

        # Build filter
        filter_dict = {}
        if assignee_id:
            filter_dict["assignee_id"] = assignee_id
        if cell_type_id:
            filter_dict["notebook_item_type_id"] = cell_type_id
        if state:
            filter_dict["estado"] = state

        # Fetch cells
        cells = db.find_many("cells", Cell, is_canonical=False, **filter_dict)

        # Limit results
        cells = cells[:limit]

        return {
            "success": True,
            "cells": [
                {
                    "id": cell.id,
                    "assignee_id": cell.assignee_id,
                    "cell_type_id": cell.notebook_item_type_id,
                    "state": cell.status.value,
                }
                for cell in cells
            ],
            "count": len(cells),
        }

    except Exception as e:
        logger.error("Error listing cells via MCP: %s", e)
        raise


async def create_book(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new book (notebook).

    Args:
        params: {
            "title": str - Book title
            "assignee_id": str - User ID responsible
            "description": str - Optional description
            "cell_ids": list - Optional list of cell IDs to include
        }

    Returns:
        Dictionary with created book information
    """
    try:
        from ...database import db
        from ...models import Book

        title = params["title"]
        assignee_id = params["assignee_id"]
        description = params.get("description", "")
        cell_ids = params.get("cell_ids", [])

        # Create book
        book = Book(name=title, assignee_id=assignee_id, description=description)

        # Add cells if provided
        if cell_ids:
            book.cells = cell_ids

        # Store book
        db.insert("books", book, current_user=SYSTEM_USER)

        logger.info("Book created via MCP: %s", book.id)

        return {
            "success": True,
            "book_id": book.id,
            "title": title,
            "cell_count": len(cell_ids),
        }

    except Exception as e:
        logger.error("Error creating book via MCP: %s", e)
        raise


def register(server: "MCPServer") -> None:
    """
    Register cell and book management tools with MCP server.

    Args:
        server: MCPServer instance
    """
    server.register_tool(
        name="create_cell",
        description="Create a new cell in ScareVerse",
        parameters={
            "assignee_id": {
                "type": "string",
                "description": "User ID responsible for the cell",
            },
            "cell_type_id": {
                "type": "string",
                "description": "Cell type ID (optional)",
            },
            "initial_data": {
                "type": "object",
                "description": "Initial data for the cell",
            },
            "title": {"type": "string", "description": "Cell title"},
        },
        handler=create_cell,
        category="cells",
    )

    server.register_tool(
        name="execute_cell",
        description="Execute an existing cell",
        parameters={
            "cell_id": {"type": "string", "description": "Cell ID to execute"},
            "execution_params": {
                "type": "object",
                "description": "Execution parameters",
            },
        },
        handler=execute_cell,
        category="cells",
    )

    server.register_tool(
        name="get_cell",
        description="Get cell information",
        parameters={
            "cell_id": {"type": "string", "description": "Cell ID to retrieve"}
        },
        handler=get_cell,
        category="cells",
    )

    server.register_tool(
        name="list_cells",
        description="List cells with optional filtering",
        parameters={
            "assignee_id": {"type": "string", "description": "Filter by assignee"},
            "cell_type_id": {"type": "string", "description": "Filter by cell type"},
            "state": {"type": "string", "description": "Filter by state"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        handler=list_cells,
        category="cells",
    )

    server.register_tool(
        name="create_book",
        description="Create a new book (notebook)",
        parameters={
            "title": {"type": "string", "description": "Book title"},
            "assignee_id": {"type": "string", "description": "User ID responsible"},
            "description": {"type": "string", "description": "Book description"},
            "cell_ids": {"type": "array", "description": "List of cell IDs to include"},
        },
        handler=create_book,
        category="cells",
    )
