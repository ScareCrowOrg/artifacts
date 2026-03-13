"""
Discovery Service for Cell Types and Book Types
Provides efficient discovery and metadata retrieval for ScareVerse artifacts
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_real_content(base_path: Path, file_name: str) -> Optional[str]:
    """
    Intelligently resolve file content, handling:
    - Real symlinks (Linux/Mac)
    - Fake symlinks as text files (Windows/Docker issue)
    - Regular files

    Args:
        base_path: Directory containing the file
        file_name: Name of file to read (e.g., "type.json")

    Returns:
        File content as string, or None if not found
    """
    file_path = base_path / file_name

    # File doesn't exist
    if not file_path.exists():
        logger.warning("File not found: %s", file_path)
        return None

    # Read content
    try:
        content = file_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.error("Error reading file %s: %s", file_path, e)
        return None

    # Check if content is a relative path (fake symlink from Windows)
    # Pattern: ../../path/to/file or ../path/to/file
    if content.startswith("../") or content.startswith("..\\"):
        logger.debug("Detected fake symlink in %s, resolving path: %s", file_path, content)

        # Normalize path separators (Windows uses \, Unix uses /)
        normalized_path = content.replace("\\", "/")

        # Resolve relative to the file's directory
        try:
            target_path = (file_path.parent / normalized_path).resolve()

            if target_path.exists():
                logger.debug("Resolved fake symlink to: %s", target_path)
                resolved_content = target_path.read_text(encoding="utf-8")
                return resolved_content
            else:
                logger.warning("Symlink target not found: %s", target_path)
                return None
        except Exception as e:
            logger.error("Error resolving symlink path %s: %s", normalized_path, e)
            return None

    # Regular file content
    return content


def discover_types(
    base_canonical_path: Path, base_sandbox_path: Path, type_category: str
) -> List[Dict[str, Any]]:
    """
    Discover all types (cell or book) from canonical and sandbox directories.

    Args:
        base_canonical_path: Path to canonical types directory
        base_sandbox_path: Path to sandbox types directory
        type_category: "cell" or "book" for logging purposes

    Returns:
        List of type metadata dicts with id, title, description, origin
    """
    types = []

    # Scan canonical types
    if base_canonical_path.exists():
        for type_dir in base_canonical_path.iterdir():
            if type_dir.is_dir() and not type_dir.name.startswith("."):
                content = get_real_content(type_dir, "type.json")

                if content:
                    try:
                        type_def = json.loads(content)
                        types.append(
                            {
                                "id": type_dir.name,  # Use directory name (actual path), not JSON id field
                                "title": type_def.get("name", type_dir.name),
                                "description": type_def.get("description", ""),
                                "origin": "canonical",
                            }
                        )
                    except json.JSONDecodeError as e:
                        logger.warning("Invalid JSON in %s: %s", type_dir / 'type.json', e)
                        continue

    # Scan sandbox types
    if base_sandbox_path.exists():
        for type_dir in base_sandbox_path.iterdir():
            if type_dir.is_dir() and not type_dir.name.startswith("."):
                content = get_real_content(type_dir, "type.json")

                if content:
                    try:
                        type_def = json.loads(content)
                        types.append(
                            {
                                "id": type_dir.name,  # Use directory name (actual path), not JSON id field
                                "title": type_def.get("name", type_dir.name),
                                "description": type_def.get("description", ""),
                                "origin": "sandbox",
                            }
                        )
                    except json.JSONDecodeError as e:
                        logger.warning("Invalid JSON in %s: %s", type_dir / 'type.json', e)
                        continue

    # Sort by title for consistent UX
    types.sort(key=lambda x: x["title"])

    logger.info("Discovered %s %s types (canonical + sandbox)", len(types), type_category)

    return types


def get_type_definition(
    type_id: str, base_canonical_path: Path, base_sandbox_path: Path
) -> Optional[Dict[str, Any]]:
    """
    Get full type definition for a specific type ID.

    Searches in order:
    1. canonical/{type_category}_types/{type_id}/type.json
    2. sandbox/{type_category}_types/{type_id}/type.json

    Args:
        type_id: Type identifier
        base_canonical_path: Path to canonical types directory
        base_sandbox_path: Path to sandbox types directory

    Returns:
        Parsed JSON type definition or None if not found
    """
    # Try canonical first
    canonical_dir = base_canonical_path / type_id
    content = get_real_content(canonical_dir, "type.json")

    # Try sandbox if not found in canonical
    if not content:
        sandbox_dir = base_sandbox_path / type_id
        content = get_real_content(sandbox_dir, "type.json")

    if not content:
        return None

    # Parse JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in type definition for %s: %s", type_id, e)
        return None
