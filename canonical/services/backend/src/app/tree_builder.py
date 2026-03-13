"""
Directory tree builder with caching and filtering.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Constants for path handling
ROOT_PATH_INDICATORS = (".", "/", "")


class TreeBuilder:
    """
    Builds and caches directory tree structures.
    """

    def __init__(self, root_path: str):
        """
        Initialize tree builder.

        Args:
            root_path: Root directory to build trees from
        """
        self.root_path = Path(root_path)
        self.cache: Optional[Dict[str, Any]] = None
        self.cache_time: float = 0
        self.cache_ttl: int = 60  # seconds

    def _should_ignore(self, path: Path) -> bool:
        """
        Check if a path should be ignored.

        Args:
            path: Path to check

        Returns:
            True if should be ignored, False otherwise
        """
        ignore_patterns = {
            "__pycache__",
            ".git",
            ".gitignore",
            "node_modules",
            ".DS_Store",
            "venv",
            "env",
            ".venv",
            ".env",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".Python",
            "dist",
            "build",
            "*.egg-info",
            ".pytest_cache",
            ".mypy_cache",
            ".coverage",
            "htmlcov",
        }

        name = path.name

        # Check exact matches
        if name in ignore_patterns:
            return True

        # Check pattern matches (simple glob)
        for pattern in ignore_patterns:
            if "*" in pattern:
                ext = pattern.replace("*", "")
                if name.endswith(ext):
                    return True

        return False

    def _build_tree_recursive(
        self,
        path: Path,
        include_hidden: bool = False,
        max_depth: Optional[int] = None,
        current_depth: int = 0,
    ) -> Dict[str, Any]:
        """
        Recursively build directory tree.

        Args:
            path: Current path to process
            include_hidden: Include hidden files (starting with .)
            max_depth: Maximum depth to traverse (None = unlimited)
            current_depth: Current recursion depth

        Returns:
            Dictionary representing the tree structure
        """
        if max_depth is not None and current_depth >= max_depth:
            return {}

        node: Dict[str, Any] = {
            "name": path.name,
            "path": str(path.relative_to(self.root_path))
            if path != self.root_path
            else ".",
            "type": "directory" if path.is_dir() else "file",
        }

        # Add file metadata
        if path.is_file():
            try:
                stat = path.stat()
                node["size"] = stat.st_size
                node["modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            except:
                pass

        # Recursively process directories
        if path.is_dir():
            children = []
            try:
                for child in sorted(path.iterdir()):
                    # Skip hidden files if requested
                    if not include_hidden and child.name.startswith("."):
                        continue

                    # Skip ignored patterns
                    if self._should_ignore(child):
                        continue

                    child_node = self._build_tree_recursive(
                        child, include_hidden, max_depth, current_depth + 1
                    )

                    if child_node:
                        children.append(child_node)

                node["children"] = children
                node["count"] = len(children)
            except PermissionError:
                node["error"] = "Permission denied"

        return node

    def build_tree(
        self,
        include_hidden: bool = False,
        max_depth: Optional[int] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Build directory tree with optional caching.

        Args:
            include_hidden: Include hidden files
            max_depth: Maximum depth to traverse
            use_cache: Use cached tree if available and fresh

        Returns:
            Dictionary representing the tree structure
        """
        # Check cache
        if use_cache and self.cache is not None:
            age = time.time() - self.cache_time
            if age < self.cache_ttl:
                return self.cache

        # Build fresh tree
        if not self.root_path.exists():
            self.root_path.mkdir(parents=True, exist_ok=True)

        tree = self._build_tree_recursive(self.root_path, include_hidden, max_depth, 0)

        # Cache result
        self.cache = tree
        self.cache_time = time.time()

        return tree

    def refresh_cache(self) -> None:
        """Force cache refresh on next build."""
        self.cache = None
        self.cache_time = 0

    def build_subtree(
        self,
        relative_path: str,
        include_hidden: bool = False,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Build tree starting from specific subdirectory.

        Args:
            relative_path: Relative path from root to start from
            include_hidden: Include hidden files
            max_depth: Maximum depth to traverse

        Returns:
            Dictionary representing the subtree structure
        """
        # Determine target path
        if not relative_path or relative_path in ROOT_PATH_INDICATORS:
            # Empty or root - use build_tree for full tree
            return self.build_tree(include_hidden, max_depth, use_cache=True)

        # Build path from root
        target_path = self.root_path / relative_path.strip("/")

        # Validate that target path exists and is within root
        if not target_path.exists():
            return {
                "name": relative_path,
                "path": relative_path,
                "type": "directory",
                "error": "Path does not exist",
                "children": [],
            }

        try:
            # Resolve to absolute path and check it's within root
            resolved = target_path.resolve()
            root_resolved = self.root_path.resolve()

            if not str(resolved).startswith(str(root_resolved)):
                return {
                    "name": relative_path,
                    "path": relative_path,
                    "type": "directory",
                    "error": "Path outside root directory",
                    "children": [],
                }
        except Exception:
            return {
                "name": relative_path,
                "path": relative_path,
                "type": "directory",
                "error": "Invalid path",
                "children": [],
            }

        # Build subtree from target path
        return self._build_tree_recursive(target_path, include_hidden, max_depth, 0)

    def get_flat_list(
        self, include_hidden: bool = False, file_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a flat list of all files/directories.

        Args:
            include_hidden: Include hidden files
            file_type: Filter by type ('file' or 'directory')

        Returns:
            List of file/directory information
        """
        tree = self.build_tree(include_hidden=include_hidden, use_cache=True)

        def flatten(node: Dict[str, Any]) -> List[Dict[str, Any]]:
            items = []

            # Add current node if it matches filter
            if file_type is None or node.get("type") == file_type:
                items.append(
                    {
                        "name": node["name"],
                        "path": node["path"],
                        "type": node["type"],
                        "size": node.get("size"),
                        "modified": node.get("modified"),
                    }
                )

            # Recursively process children
            for child in node.get("children", []):
                items.extend(flatten(child))

            return items

        return flatten(tree)
