"""
LangChain Runtime Tools for AgenteLab

Provides file system interaction tools for AI agents to search and read
repository contents during chat conversations.

These tools wrap the existing MCP tools to make them available to LangGraph.
"""

import json
import logging
from typing import Any, Dict

from langchain_core.tools import Tool

from .mcp.tools import file_tools, repo_tools

logger = logging.getLogger(__name__)


class RuntimeTools:
    """LangChain tools for runtime file operations."""

    @staticmethod
    async def grep_impl(
        pattern: str,
        path: str = ".",
        file_pattern: str = None,
        case_sensitive: bool = False,
        max_results: int = 100,
    ) -> Dict[str, Any]:
        """
        Search for text patterns within files (grep).

        Args:
            pattern: Search pattern
            path: Directory to search (default: ".")
            file_pattern: Filter by file pattern (e.g., "*.py")
            case_sensitive: Case sensitive search
            max_results: Maximum results to return

        Returns:
            Dictionary with search results
        """
        try:
            params = {
                "query": pattern,
                "path": path,
                "file_pattern": file_pattern,
                "case_sensitive": case_sensitive,
                "max_results": max_results,
            }

            result = await repo_tools.search_code(params)

            logger.info("[RUNTIME] grep executed: pattern='%s', found=%s matches", pattern, result.get('count', 0))

            return {"success": True, "command": "grep", "data": result}

        except Exception as e:
            logger.error("[RUNTIME] grep failed: %s", e)
            return {"success": False, "command": "grep", "error": str(e)}

    @staticmethod
    async def find_impl(
        pattern: str, path: str = ".", recursive: bool = True
    ) -> Dict[str, Any]:
        """
        Find files by name pattern (glob).

        Args:
            pattern: File pattern (glob syntax, e.g., "*.py")
            path: Starting directory (default: ".")
            recursive: Recursive search

        Returns:
            Dictionary with matching files
        """
        try:
            params = {"pattern": pattern, "path": path, "recursive": recursive}

            result = await file_tools.search_files(params)

            logger.info("[RUNTIME] find executed: pattern='%s', found=%s files", pattern, result.get('count', 0))

            return {"success": True, "command": "find", "data": result}

        except Exception as e:
            logger.error("[RUNTIME] find failed: %s", e)
            return {"success": False, "command": "find", "error": str(e)}

    @staticmethod
    async def read_file_impl(
        path: str, encoding: str = "utf-8", max_size_mb: int = 10
    ) -> Dict[str, Any]:
        """
        Read file contents.

        Args:
            path: Relative path to file
            encoding: File encoding (default: "utf-8")
            max_size_mb: Max file size in MB (default: 10)

        Returns:
            Dictionary with file contents and metadata
        """
        try:
            params = {"path": path, "encoding": encoding, "max_size_mb": max_size_mb}

            result = await file_tools.read_file(params)

            logger.info("[RUNTIME] read_file executed: path='%s', size=%s bytes", path, result.get('size', 0))

            return {"success": True, "command": "read", "data": result}

        except Exception as e:
            logger.error("[RUNTIME] read_file failed: %s", e)
            return {"success": False, "command": "read", "error": str(e)}

    @staticmethod
    async def list_directory_impl(
        path: str = ".", include_hidden: bool = False, recursive: bool = False
    ) -> Dict[str, Any]:
        """
        List directory contents.

        Args:
            path: Directory path (default: ".")
            include_hidden: Include hidden files
            recursive: Recursive listing

        Returns:
            Dictionary with directory contents
        """
        try:
            params = {
                "path": path,
                "include_hidden": include_hidden,
                "recursive": recursive,
            }

            result = await file_tools.list_directory(params)

            logger.info("[RUNTIME] list_directory executed: path='%s', items=%s", path, result.get('count', 0))

            return {"success": True, "command": "list", "data": result}

        except Exception as e:
            logger.error("[RUNTIME] list_directory failed: %s", e)
            return {"success": False, "command": "list", "error": str(e)}

    @staticmethod
    def grep_tool() -> Tool:
        """
        Create a LangChain Tool for grep (search content in files).

        Returns:
            LangChain Tool instance
        """

        async def _grep_async(input_str: str) -> str:
            """
            Async tool function for grep.
            Input format: JSON string with {pattern, path?, file_pattern?, case_sensitive?, max_results?}
            """
            try:
                params = json.loads(input_str)
                pattern = params.get("pattern")

                if not pattern:
                    return json.dumps(
                        {"error": "Missing required parameter: 'pattern'"}
                    )

                result = await RuntimeTools.grep_impl(
                    pattern=pattern,
                    path=params.get("path", "."),
                    file_pattern=params.get("file_pattern"),
                    case_sensitive=params.get("case_sensitive", False),
                    max_results=params.get("max_results", 100),
                )

                return json.dumps(result, ensure_ascii=False)

            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid JSON input"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        return Tool(
            name="grep",
            description=(
                "Search for text patterns within files. "
                "Input: JSON string with {pattern: str (required), path: str (default '.'), "
                "file_pattern: str (e.g., '*.py'), case_sensitive: bool, max_results: int}. "
                'Example: {"pattern": "async def", "path": "backend/app", "file_pattern": "*.py"}'
            ),
            func=lambda x: "Use coroutine instead",
            coroutine=_grep_async,
        )

    @staticmethod
    def find_tool() -> Tool:
        """
        Create a LangChain Tool for find (search files by pattern).

        Returns:
            LangChain Tool instance
        """

        async def _find_async(input_str: str) -> str:
            """
            Async tool function for find.
            Input format: JSON string with {pattern, path?, recursive?}
            """
            try:
                params = json.loads(input_str)
                pattern = params.get("pattern")

                if not pattern:
                    return json.dumps(
                        {"error": "Missing required parameter: 'pattern'"}
                    )

                result = await RuntimeTools.find_impl(
                    pattern=pattern,
                    path=params.get("path", "."),
                    recursive=params.get("recursive", True),
                )

                return json.dumps(result, ensure_ascii=False)

            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid JSON input"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        return Tool(
            name="find",
            description=(
                "Find files by name pattern (glob). "
                "Input: JSON string with {pattern: str (required), path: str (default '.'), "
                "recursive: bool (default true)}. "
                'Example: {"pattern": "test_*.py", "path": "backend/tests", "recursive": true}'
            ),
            func=lambda x: "Use coroutine instead",
            coroutine=_find_async,
        )

    @staticmethod
    def read_file_tool() -> Tool:
        """
        Create a LangChain Tool for reading file contents.

        Returns:
            LangChain Tool instance
        """

        async def _read_file_async(input_str: str) -> str:
            """
            Async tool function for read_file.
            Input format: JSON string with {path, encoding?, max_size_mb?}
            """
            try:
                params = json.loads(input_str)
                path = params.get("path")

                if not path:
                    return json.dumps({"error": "Missing required parameter: 'path'"})

                result = await RuntimeTools.read_file_impl(
                    path=path,
                    encoding=params.get("encoding", "utf-8"),
                    max_size_mb=params.get("max_size_mb", 10),
                )

                return json.dumps(result, ensure_ascii=False)

            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid JSON input"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        return Tool(
            name="read_file",
            description=(
                "Read the contents of a file. "
                "Input: JSON string with {path: str (required), encoding: str (default 'utf-8'), "
                "max_size_mb: int (default 10)}. "
                'Example: {"path": "README.md"}'
            ),
            func=lambda x: "Use coroutine instead",
            coroutine=_read_file_async,
        )

    @staticmethod
    def list_directory_tool() -> Tool:
        """
        Create a LangChain Tool for listing directory contents.

        Returns:
            LangChain Tool instance
        """

        async def _list_directory_async(input_str: str) -> str:
            """
            Async tool function for list_directory.
            Input format: JSON string with {path?, include_hidden?, recursive?}
            """
            try:
                params = json.loads(input_str)

                result = await RuntimeTools.list_directory_impl(
                    path=params.get("path", "."),
                    include_hidden=params.get("include_hidden", False),
                    recursive=params.get("recursive", False),
                )

                return json.dumps(result, ensure_ascii=False)

            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid JSON input"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        return Tool(
            name="list_directory",
            description=(
                "List files and directories in a path. "
                "Input: JSON string with {path: str (default '.'), include_hidden: bool, "
                "recursive: bool}. "
                'Example: {"path": "backend/app", "recursive": false}'
            ),
            func=lambda x: "Use coroutine instead",
            coroutine=_list_directory_async,
        )


def get_runtime_tools() -> list[Tool]:
    """
    Get all available runtime tools for AgenteLab.

    Returns:
        List of LangChain Tool instances
    """
    return [
        RuntimeTools.grep_tool(),
        RuntimeTools.find_tool(),
        RuntimeTools.read_file_tool(),
        RuntimeTools.list_directory_tool(),
    ]


def get_runtime_tool_definitions() -> list[Dict[str, Any]]:
    """
    Get runtime tool definitions in OpenAI function calling format.

    Used for OpenAI-compatible LLMs that support function calling.

    Returns:
        List of tool definitions in OpenAI format
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "grep",
                "description": "Search for text patterns within files. Use this to find code, TODOs, or any text content in the repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Text pattern to search for",
                        },
                        "path": {
                            "type": "string",
                            "description": "Directory to search in (default: '.')",
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "Filter by file pattern, e.g., '*.py', '*.js'",
                        },
                        "case_sensitive": {
                            "type": "boolean",
                            "description": "Case sensitive search (default: false)",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 100)",
                        },
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find",
                "description": "Find files by name pattern (glob). Use this to locate files in the repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "File pattern (glob syntax), e.g., '*.py', 'test_*.js'",
                        },
                        "path": {
                            "type": "string",
                            "description": "Starting directory (default: '.')",
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Recursive search (default: true)",
                        },
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file. Use this to examine source code, configuration, or documentation files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path to the file",
                        },
                        "encoding": {
                            "type": "string",
                            "description": "File encoding (default: 'utf-8')",
                        },
                        "max_size_mb": {
                            "type": "integer",
                            "description": "Maximum file size in MB (default: 10)",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List files and directories in a path. Use this to explore the repository structure.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path (default: '.')",
                        },
                        "include_hidden": {
                            "type": "boolean",
                            "description": "Include hidden files (default: false)",
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Recursive listing (default: false)",
                        },
                    },
                    "required": [],
                },
            },
        },
    ]
