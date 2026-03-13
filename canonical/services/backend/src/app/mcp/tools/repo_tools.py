"""
Repository Navigation Tools for MCP

Tools for browsing and searching the ScareVerse codebase.
"""

import logging
import re
import subprocess
from glob import glob
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


def _is_regex_pattern(pattern: str) -> bool:
    """
    Detect if a pattern contains regex metacharacters.

    Args:
        pattern: Pattern string to check

    Returns:
        True if pattern contains regex metacharacters
    """
    regex_metacharacters = r"[\](){}|+*?^$.\\"
    return any(char in pattern for char in regex_metacharacters)


def _validate_regex_pattern(pattern: str) -> None:
    """
    Validate a regex pattern by attempting to compile it.

    Args:
        pattern: Regex pattern to validate

    Raises:
        ValueError: If pattern is invalid regex
    """
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}") from e


def _expand_path_wildcards(path: str, base_dir: Path) -> List[Path]:
    """
    Expand wildcards in path parameter.

    Args:
        path: Path pattern (may contain *, ?, [])
        base_dir: Base directory to expand from

    Returns:
        List of resolved paths

    Raises:
        ValueError: If any expanded path is outside base_dir
    """
    # Check if path contains wildcards
    if "*" in path or "?" in path or "[" in path:
        # Create absolute pattern
        pattern = str(base_dir / path)

        # Expand wildcards
        expanded = glob(pattern, recursive=("**" in path))

        if not expanded:
            # No matches - return empty list (not an error)
            return []

        # Convert to Path objects and validate security
        result_paths = []
        for expanded_path in expanded:
            resolved = Path(expanded_path).resolve()

            # Security check: ensure path is within BASE_DIR
            # Use more robust path comparison to prevent bypass attempts
            try:
                resolved.relative_to(base_dir)
            except ValueError:
                raise ValueError(
                    f"Access denied: expanded path outside project directory: {expanded_path}"
                )

            result_paths.append(resolved)

        return result_paths
    else:
        # No wildcards - return single resolved path
        return [(base_dir / path).resolve()]


async def search_code(params: Dict[str, Any]) -> Dict[str, Any]:
    r"""
    Search for code patterns in the repository.

    Supports regex patterns and path wildcards.

    Args:
        params: {
            "query": str - Search query (supports regex if pattern contains metacharacters)
            "path": str - Path to search in (supports wildcards: *, ?, [])
            "file_pattern": str - Optional file pattern (e.g., "*.py")
            "case_sensitive": bool - Case sensitive search
            "max_results": int - Maximum results (default: 100)
        }

    Returns:
        Dictionary with search results

    Examples:
        # Simple string search
        {"query": "TODO", "path": "backend/app"}

        # Regex search (OR operator)
        {"query": "foo|bar", "path": "."}

        # Path wildcards
        {"query": "import", "path": "backend/*/routers"}

        # Combined regex + wildcards
        {"query": "^class\\s+", "path": "**/models/*.py"}
    """
    try:
        query = params["query"]
        search_path = params.get("path", ".")
        file_pattern = params.get("file_pattern")
        case_sensitive = params.get("case_sensitive", False)
        max_results = params.get("max_results", 100)

        logger.info(
            "[SEARCH_CODE] Starting search: query=%s, path=%s, file_pattern=%s",
            query, search_path, file_pattern
        )

        # Detect and validate regex patterns
        is_regex = _is_regex_pattern(query)
        if is_regex:
            logger.info("[SEARCH_CODE] Detected regex pattern in query")
            _validate_regex_pattern(query)

        # Expand path wildcards
        try:
            target_paths = _expand_path_wildcards(search_path, BASE_DIR)
        except ValueError as e:
            # Re-raise security errors
            raise e

        if not target_paths:
            # No paths matched - return empty results
            logger.info("[SEARCH_CODE] No paths matched pattern: %s", search_path)
            return {"query": query, "matches": [], "count": 0, "truncated": False}

        logger.info("[SEARCH_CODE] Expanded %s to %s path(s)", search_path, len(target_paths))

        # Collect all matches from all target paths
        all_matches = []

        for target_path in target_paths:
            # Check if path exists
            if not target_path.exists():
                logger.warning("[SEARCH_CODE] Skipping non-existent path: %s", target_path)
                continue

            # Security check already done in _expand_path_wildcards, but double-check
            if not str(target_path).startswith(str(BASE_DIR)):
                logger.error("[SEARCH_CODE] Path traversal attempt: %s not in %s", target_path, BASE_DIR)
                raise ValueError("Access denied: path outside project directory")

            # Build grep command based on whether target is file or directory
            is_file = target_path.is_file()
            is_dir = target_path.is_dir()

            logger.info("[SEARCH_CODE] Processing: %s (is_file=%s, is_dir=%s)", target_path, is_file, is_dir)

            if is_file:
                # For files, use grep without -r flag
                cmd = ["grep", "-n"]  # -n for line numbers

                # Add regex flag if needed
                if is_regex:
                    cmd.append("-E")  # Extended regex

                if not case_sensitive:
                    cmd.append("-i")

                cmd.extend([query, str(target_path)])

            elif is_dir:
                # For directories, use grep with -r flag
                cmd = ["grep", "-rn"]  # -r for recursive, -n for line numbers

                # Add regex flag if needed
                if is_regex:
                    cmd.append("-E")  # Extended regex

                if not case_sensitive:
                    cmd.append("-i")

                if file_pattern:
                    cmd.extend(["--include", file_pattern])

                cmd.extend([query, str(target_path)])

            else:
                logger.warning("[SEARCH_CODE] Skipping: path is neither file nor directory: %s", target_path)
                continue

            logger.info("[SEARCH_CODE] Executing command: %s", ' '.join(cmd))

            # Execute search
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            logger.info(
                "[SEARCH_CODE] Command completed: return_code=%s, stdout_lines=%s",
                result.returncode, len(result.stdout.splitlines())
            )

            # Parse results for this path
            for line in result.stdout.splitlines():
                if ":" in line:
                    parts = line.split(":", 2)

                    # When grep searches a single file, output is: line:content
                    # When grep searches directory, output is: path:line:content
                    # We need to detect which format we have

                    # Check if first part is a valid line number (single file format)
                    if parts[0].isdigit() and is_file:
                        # Single file format: line:content
                        # Use the target_path as the file
                        file_path = target_path.relative_to(BASE_DIR)
                        line_number = int(parts[0])
                        # Content is everything after the first colon
                        content = ":".join(parts[1:]).strip() if len(parts) > 1 else ""

                    elif len(parts) >= 3:
                        # Directory format: path:line:content
                        try:
                            file_path = Path(parts[0]).relative_to(BASE_DIR)
                        except ValueError:
                            # If path is already relative, use it as is
                            file_path = Path(parts[0])
                        line_number = int(parts[1]) if parts[1].isdigit() else 0
                        content = parts[2].strip()

                    else:
                        # Skip malformed lines
                        continue

                    all_matches.append(
                        {
                            "file": str(file_path),
                            "line": line_number,
                            "content": content,
                        }
                    )

        # Apply max_results limit to combined results
        truncated = len(all_matches) > max_results
        final_matches = all_matches[:max_results]

        return {
            "query": query,
            "matches": final_matches,
            "count": len(final_matches),
            "truncated": truncated,
        }

    except subprocess.TimeoutExpired:
        raise ValueError("Search timed out")
    except Exception as e:
        logger.error("Error searching code: %s", e)
        raise


async def get_project_structure(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a tree view of the project structure.

    Args:
        params: {
            "path": str - Starting path (default: ".")
            "max_depth": int - Maximum depth (default: 3)
            "include_hidden": bool - Include hidden files
        }

    Returns:
        Dictionary with project structure
    """
    try:
        # Try to import tree_builder if available
        # Note: tree_builder is an optional module. If not available, fallback to simple listing.
        from ...tree_builder import build_tree

        rel_path = params.get("path", ".")
        max_depth = params.get("max_depth", 3)
        include_hidden = params.get("include_hidden", False)

        # Resolve path
        target_path = (BASE_DIR / rel_path).resolve()

        if not str(target_path).startswith(str(BASE_DIR)):
            raise ValueError("Access denied: path outside project directory")

        # Build tree structure (if tree_builder exists)
        tree = build_tree(
            str(target_path), max_depth=max_depth, include_hidden=include_hidden
        )

        return {"path": rel_path, "structure": tree}

    except ImportError:
        # Fallback: tree_builder not available
        return {
            "path": params.get("path", "."),
            "error": "Tree builder module not available, use list_directory instead",
        }
    except Exception as e:
        logger.error("Error getting project structure: %s", e)
        raise


async def get_file_info(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get detailed information about a file.

    Args:
        params: {
            "path": str - Relative path to file
        }

    Returns:
        Dictionary with file information
    """
    try:
        rel_path = params["path"]

        # Resolve path
        file_path = (BASE_DIR / rel_path).resolve()

        if not str(file_path).startswith(str(BASE_DIR)):
            raise ValueError("Access denied: path outside project directory")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {rel_path}")

        # Get file stats
        stat = file_path.stat()

        info = {
            "path": rel_path,
            "name": file_path.name,
            "type": "directory" if file_path.is_dir() else "file",
            "size": stat.st_size,
            "modified": stat.st_mtime,
        }

        # Get line count for text files
        if file_path.is_file():
            try:
                content = file_path.read_text()
                info["lines"] = len(content.splitlines())
                info["is_text"] = True
            except (UnicodeDecodeError, PermissionError):
                info["is_text"] = False

        return info

    except Exception as e:
        logger.error("Error getting file info: %s", e)
        raise


def register(server: "MCPServer") -> None:
    """
    Register repository navigation tools with MCP server.

    Args:
        server: MCPServer instance
    """
    server.register_tool(
        name="search_code",
        description="Search for code patterns in the repository",
        parameters={
            "query": {"type": "string", "description": "Search query"},
            "path": {"type": "string", "description": "Path to search in"},
            "file_pattern": {
                "type": "string",
                "description": "File pattern (e.g., '*.py')",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case sensitive search",
            },
            "max_results": {"type": "integer", "description": "Maximum results"},
        },
        handler=search_code,
        category="repository",
    )

    server.register_tool(
        name="get_project_structure",
        description="Get a tree view of the project structure",
        parameters={
            "path": {"type": "string", "description": "Starting path"},
            "max_depth": {"type": "integer", "description": "Maximum depth"},
            "include_hidden": {
                "type": "boolean",
                "description": "Include hidden files",
            },
        },
        handler=get_project_structure,
        category="repository",
    )

    server.register_tool(
        name="get_file_info",
        description="Get detailed information about a file",
        parameters={"path": {"type": "string", "description": "Relative path to file"}},
        handler=get_file_info,
        category="repository",
    )
