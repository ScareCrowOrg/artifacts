"""
File System Tools for MCP

Tools for file and directory operations within the ScareVerse repository.
"""

import logging
import os
from glob import glob as glob_pattern
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from ..server import MCPServer

logger = logging.getLogger(__name__)

# Import BASE_DIR from centralized config for consistency
try:
    from ...config.database import BASE_DIR
except ImportError:
    # Fallback if config not available (should not happen in normal operation)
    logger.warning("Could not import BASE_DIR from config, using fallback calculation")
    BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent


async def list_directory(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    List files and directories in a given path.

    Args:
        params: {
            "path": str - Relative path from project root (default: ".")
            "include_hidden": bool - Include hidden files (default: False)
            "recursive": bool - Recursive listing (default: False)
        }

    Returns:
        Dictionary with directory contents
    """
    try:
        rel_path = params.get("path", ".")
        include_hidden = params.get("include_hidden", False)
        recursive = params.get("recursive", False)

        # Resolve and validate path (security)
        target_path = (BASE_DIR / rel_path).resolve()

        if not str(target_path).startswith(str(BASE_DIR)):
            raise ValueError("Access denied: path outside project directory")

        if not target_path.exists():
            raise FileNotFoundError(f"Path not found: {rel_path}")

        if not target_path.is_dir():
            raise ValueError(f"Path is not a directory: {rel_path}")

        # List contents
        contents = []

        if recursive:
            for root, dirs, files in os.walk(target_path):
                rel_root = Path(root).relative_to(BASE_DIR)

                if not include_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    files = [f for f in files if not f.startswith(".")]

                for name in dirs:
                    contents.append(
                        {
                            "name": name,
                            "path": str(rel_root / name),
                            "type": "directory",
                        }
                    )

                for name in files:
                    file_path = Path(root) / name
                    contents.append(
                        {
                            "name": name,
                            "path": str(rel_root / name),
                            "type": "file",
                            "size": file_path.stat().st_size,
                        }
                    )
        else:
            for item in target_path.iterdir():
                if not include_hidden and item.name.startswith("."):
                    continue

                rel_item_path = item.relative_to(BASE_DIR)

                item_info = {
                    "name": item.name,
                    "path": str(rel_item_path),
                    "type": "directory" if item.is_dir() else "file",
                }

                if item.is_file():
                    item_info["size"] = item.stat().st_size

                contents.append(item_info)

        return {"path": rel_path, "items": contents, "count": len(contents)}

    except Exception as e:
        logger.error("Error listing directory: %s", e)
        raise


async def read_file(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Read file contents with optional line numbers and multi-file support.

    Args:
        params: {
            "path": str - Relative path to file (single file)
            "paths": str or List[str] - Multiple file paths (comma-separated or list)
            "encoding": str - File encoding (default: "utf-8")
            "max_size_mb": int - Max file size in MB (default: 10)
            "line_numbers": bool - Include line numbers in content (default: False)
        }

    Returns:
        Dictionary with file contents (single file) or list of files (multiple files)
    """
    try:
        encoding = params.get("encoding", "utf-8")
        max_size_mb = params.get("max_size_mb", 10)
        line_numbers = params.get("line_numbers", False)

        # Determine if single or multiple files
        paths = None
        if "paths" in params:
            # Multiple files mode
            paths_param = params["paths"]
            if isinstance(paths_param, str):
                # Split comma-separated string
                paths = [p.strip() for p in paths_param.split(",") if p.strip()]
            elif isinstance(paths_param, list):
                paths = paths_param
            else:
                raise ValueError("'paths' must be a string or list")
        elif "path" in params:
            # Single file mode (for backward compatibility)
            paths = [params["path"]]
        else:
            raise ValueError("Either 'path' or 'paths' parameter is required")

        # Limit number of files to prevent abuse
        MAX_FILES = 10
        if len(paths) > MAX_FILES:
            raise ValueError(f"Too many files requested. Maximum: {MAX_FILES}")

        # Read all files
        results = []
        for rel_path in paths:
            # Resolve and validate path
            file_path = (BASE_DIR / rel_path).resolve()

            if not str(file_path).startswith(str(BASE_DIR)):
                raise ValueError(
                    f"Access denied: path outside project directory: {rel_path}"
                )

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {rel_path}")

            if not file_path.is_file():
                raise ValueError(f"Path is not a file: {rel_path}")

            # Check file size
            file_size = file_path.stat().st_size
            max_bytes = max_size_mb * 1024 * 1024

            if file_size > max_bytes:
                raise ValueError(
                    f"File too large: {file_size / 1024 / 1024:.2f}MB "
                    f"(max: {max_size_mb}MB) - {rel_path}"
                )

            # Read file
            content = file_path.read_text(encoding=encoding)

            # Add line numbers if requested
            if line_numbers:
                lines = content.splitlines()
                # Format: "1: first line\n2: second line\n..."
                numbered_lines = [f"{i + 1}: {line}" for i, line in enumerate(lines)]
                content = "\n".join(numbered_lines)

            results.append(
                {
                    "path": rel_path,
                    "content": content,
                    "size": file_size,
                    "encoding": encoding,
                    "lines": len(content.splitlines()),
                    "line_numbers": line_numbers,
                }
            )

        # Return format depends on whether single or multiple files were requested
        if len(results) == 1 and "path" in params:
            # Single file mode - return directly for backward compatibility
            return results[0]
        else:
            # Multiple files mode - return array
            return {"files": results, "count": len(results)}

    except Exception as e:
        logger.error("Error reading file: %s", e)
        raise


async def write_file(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Write content to a file.

    Args:
        params: {
            "path": str - Relative path to file
            "content": str - Content to write
            "encoding": str - File encoding (default: "utf-8")
            "create_dirs": bool - Create parent directories (default: True)
        }

    Returns:
        Dictionary with write result
    """
    try:
        rel_path = params["path"]
        content = params["content"]
        encoding = params.get("encoding", "utf-8")
        create_dirs = params.get("create_dirs", True)

        # Resolve and validate path
        file_path = (BASE_DIR / rel_path).resolve()

        if not str(file_path).startswith(str(BASE_DIR)):
            raise ValueError("Access denied: path outside project directory")

        # Create parent directories if needed
        if create_dirs and not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        file_path.write_text(content, encoding=encoding)

        return {
            "path": rel_path,
            "size": len(content.encode(encoding)),
            "lines": len(content.splitlines()),
        }

    except Exception as e:
        logger.error("Error writing file: %s", e)
        raise


async def create_directory(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new directory.

    Args:
        params: {
            "path": str - Relative path for new directory
            "parents": bool - Create parent directories (default: True)
        }

    Returns:
        Dictionary with creation result
    """
    try:
        rel_path = params["path"]
        parents = params.get("parents", True)

        # Resolve and validate path
        dir_path = (BASE_DIR / rel_path).resolve()

        if not str(dir_path).startswith(str(BASE_DIR)):
            raise ValueError("Access denied: path outside project directory")

        if dir_path.exists():
            raise ValueError(f"Directory already exists: {rel_path}")

        # Create directory
        dir_path.mkdir(parents=parents, exist_ok=False)

        return {"path": rel_path, "created": True}

    except Exception as e:
        logger.error("Error creating directory: %s", e)
        raise


async def read_file_snippet(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Read a snippet from a file by line range.

    Args:
        params: {
            "path": str - Relative path to file
            "start_line": int - Starting line number (1-indexed, inclusive)
            "end_line": int - Ending line number (1-indexed, inclusive)
            "encoding": str - File encoding (default: "utf-8")
            "context_lines": int - Additional context lines before/after (default: 0)
        }

    Returns:
        Dictionary with snippet content and metadata
    """
    try:
        rel_path = params["path"]
        start_line = params["start_line"]
        end_line = params["end_line"]
        encoding = params.get("encoding", "utf-8")
        context_lines = params.get("context_lines", 0)

        # Validate line numbers
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            raise ValueError("start_line and end_line must be integers")

        if start_line < 1 or end_line < 1:
            raise ValueError("Line numbers must be positive (1-indexed)")

        if start_line > end_line:
            raise ValueError("start_line must be <= end_line")

        # Resolve and validate path
        file_path = (BASE_DIR / rel_path).resolve()

        if not str(file_path).startswith(str(BASE_DIR)):
            raise ValueError("Access denied: path outside project directory")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {rel_path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {rel_path}")

        # Read file and split into lines
        content = file_path.read_text(encoding=encoding)
        lines = content.splitlines()
        total_lines = len(lines)

        # Special case: Allow appending new lines (start_line == total_lines + 1)
        # This enables inserting content after the last line of the file
        if start_line == total_lines + 1 and end_line >= start_line:
            # Append mode: return empty content for original
            return {
                "path": rel_path,
                "start_line": start_line,
                "end_line": end_line,
                "actual_start": start_line,
                "actual_end": end_line,
                "content": "",
                "lines": 0,
                "total_file_lines": total_lines,
                "context_lines": context_lines,
                "encoding": encoding,
                "append_mode": True,
            }

        # Validate line range is within file bounds
        if start_line > total_lines:
            raise ValueError(
                f"start_line ({start_line}) exceeds file length ({total_lines} lines)"
            )

        if end_line > total_lines:
            raise ValueError(
                f"end_line ({end_line}) exceeds file length ({total_lines} lines)"
            )

        # Calculate actual range with context
        actual_start = max(1, start_line - context_lines)
        actual_end = min(total_lines, end_line + context_lines)

        # Extract snippet (convert to 0-indexed for array slicing)
        snippet_lines = lines[actual_start - 1 : actual_end]
        snippet_content = "\n".join(snippet_lines)

        return {
            "path": rel_path,
            "start_line": start_line,
            "end_line": end_line,
            "actual_start": actual_start,
            "actual_end": actual_end,
            "content": snippet_content,
            "lines": len(snippet_lines),
            "total_file_lines": total_lines,
            "context_lines": context_lines,
            "encoding": encoding,
        }

    except Exception as e:
        logger.error("Error reading file snippet: %s", e)
        raise


def _expand_search_path_wildcards(path: str, base_dir: Path) -> List[Path]:
    """
    Expand wildcards in search path parameter.

    Args:
        path: Path pattern (may contain *, ?, [])
        base_dir: Base directory to expand from

    Returns:
        List of resolved directory paths

    Raises:
        ValueError: If any expanded path is outside base_dir or not a directory
    """
    # Check if path contains wildcards
    if "*" in path or "?" in path or "[" in path:
        # Create absolute pattern
        pattern = str(base_dir / path)

        # Expand wildcards
        expanded = glob_pattern(pattern, recursive=("**" in path))

        if not expanded:
            # No matches - return empty list (not an error)
            return []

        # Convert to Path objects, filter directories, and validate security
        result_paths = []
        for expanded_path in expanded:
            resolved = Path(expanded_path).resolve()

            # Security check: ensure path is within BASE_DIR
            if not str(resolved).startswith(str(base_dir)):
                raise ValueError(
                    f"Access denied: expanded path outside project directory: {expanded_path}"
                )

            # Only include directories for search_files
            if resolved.is_dir():
                result_paths.append(resolved)

        return result_paths
    else:
        # No wildcards - return single resolved path
        return [(base_dir / path).resolve()]


async def search_files(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for files matching a pattern.

    Supports wildcards in both pattern and path parameters.

    Args:
        params: {
            "pattern": str - Filename pattern (glob)
            "path": str - Start search from this path (default: ".", supports wildcards)
            "recursive": bool - Recursive search (default: True)
        }

    Returns:
        Dictionary with matching files

    Examples:
        # Simple pattern
        {"pattern": "*.py", "path": "backend/app"}

        # Path wildcards
        {"pattern": "*.json", "path": "backend/*/config"}

        # Recursive with wildcards
        {"pattern": "test_*.py", "path": "**/tests"}
    """
    try:
        pattern = params["pattern"]
        rel_path = params.get("path", ".")
        recursive = params.get("recursive", True)

        # Expand path wildcards
        try:
            search_paths = _expand_search_path_wildcards(rel_path, BASE_DIR)
        except ValueError as e:
            # Re-raise security errors
            raise e

        if not search_paths:
            # No paths matched - return empty results
            logger.info("[SEARCH_FILES] No paths matched pattern: %s", rel_path)
            return {
                "pattern": pattern,
                "search_path": rel_path,
                "matches": [],
                "count": 0,
            }

        logger.info("[SEARCH_FILES] Expanded %s to %s path(s)", rel_path, len(search_paths))

        # Collect all matches from all search paths
        all_results = []
        seen_paths = set()  # Avoid duplicates

        for search_path in search_paths:
            # Validate path exists
            if not search_path.exists():
                logger.warning("[SEARCH_FILES] Skipping non-existent path: %s", search_path)
                continue

            # Security check already done in _expand_search_path_wildcards, but double-check
            if not str(search_path).startswith(str(BASE_DIR)):
                raise ValueError("Access denied: path outside project directory")

            # Search files in this path
            if recursive:
                matches = list(search_path.rglob(pattern))
            else:
                matches = list(search_path.glob(pattern))

            # Add matches to results (avoiding duplicates)
            for match in matches:
                # Security check for each match - use more robust path validation
                resolved_match = match.resolve()
                try:
                    resolved_match.relative_to(BASE_DIR)
                except ValueError:
                    logger.warning("[SEARCH_FILES] Skipping match outside BASE_DIR: %s", resolved_match)
                    continue

                # Check for duplicates
                match_str = str(resolved_match)
                if match_str in seen_paths:
                    continue
                seen_paths.add(match_str)

                rel_match = resolved_match.relative_to(BASE_DIR)
                all_results.append(
                    {
                        "path": str(rel_match),
                        "name": resolved_match.name,
                        "type": "directory" if resolved_match.is_dir() else "file",
                        "size": resolved_match.stat().st_size
                        if resolved_match.is_file()
                        else None,
                    }
                )

        return {
            "pattern": pattern,
            "search_path": rel_path,
            "matches": all_results,
            "count": len(all_results),
        }

    except Exception as e:
        logger.error("Error searching files: %s", e)
        raise


def register(server: "MCPServer") -> None:
    """
    Register file system tools with MCP server.

    Args:
        server: MCPServer instance
    """
    server.register_tool(
        name="list_directory",
        description="List files and directories in a given path",
        parameters={
            "path": {
                "type": "string",
                "description": "Relative path from project root",
            },
            "include_hidden": {
                "type": "boolean",
                "description": "Include hidden files",
            },
            "recursive": {"type": "boolean", "description": "Recursive listing"},
        },
        handler=list_directory,
        category="filesystem",
    )

    server.register_tool(
        name="read_file",
        description="Read file contents",
        parameters={
            "path": {"type": "string", "description": "Relative path to file"},
            "encoding": {"type": "string", "description": "File encoding"},
            "max_size_mb": {"type": "integer", "description": "Max file size in MB"},
        },
        handler=read_file,
        category="filesystem",
    )

    server.register_tool(
        name="write_file",
        description="Write content to a file",
        parameters={
            "path": {"type": "string", "description": "Relative path to file"},
            "content": {"type": "string", "description": "Content to write"},
            "encoding": {"type": "string", "description": "File encoding"},
            "create_dirs": {
                "type": "boolean",
                "description": "Create parent directories",
            },
        },
        handler=write_file,
        category="filesystem",
    )

    server.register_tool(
        name="create_directory",
        description="Create a new directory",
        parameters={
            "path": {
                "type": "string",
                "description": "Relative path for new directory",
            },
            "parents": {"type": "boolean", "description": "Create parent directories"},
        },
        handler=create_directory,
        category="filesystem",
    )

    server.register_tool(
        name="search_files",
        description="Search for files matching a pattern",
        parameters={
            "pattern": {"type": "string", "description": "Filename pattern (glob)"},
            "path": {"type": "string", "description": "Start search from this path"},
            "recursive": {"type": "boolean", "description": "Recursive search"},
        },
        handler=search_files,
        category="filesystem",
    )
