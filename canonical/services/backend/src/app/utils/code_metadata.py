"""
Code File Metadata Management Utility

This module provides utilities for reading, writing, and merging metadata in code files
(.vue, .js, .ts) using JSDoc-style multi-line comments. The metadata is stored in a
special @metadata tag at the top of the file.

Format:
/**
 * @metadata {
 *   "processed": true,
 *   "processed_date": "2025-12-10",
 *   "themes": ["frontend", "i18n"],
 *   "modules": ["cockpit-vue"],
 *   "code_verified": true
 * }
 */

This approach ensures:
- Syntactically valid for all JavaScript/TypeScript/Vue files
- Preserves existing JSDoc comments
- Enables automated metadata tracking by agents
- Compatible with all build tools and linters
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class CodeMetadataManager:
    """Manager for reading and writing metadata in code files using JSDoc comments."""

    # Pattern to match the metadata JSDoc block
    METADATA_PATTERN = re.compile(
        r"/\*\*\s*\n?\s*\*\s*@metadata\s+({[\s\S]*?})\s*\n?\s*\*/", re.MULTILINE
    )

    # Pattern to detect if file starts with a comment block
    LEADING_COMMENT_PATTERN = re.compile(r"^\s*/\*\*", re.MULTILINE)

    @classmethod
    def read_metadata(cls, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read metadata from a code file.

        Args:
            file_path: Path to the code file (.vue, .js, .ts)

        Returns:
            Dictionary containing metadata, or None if no metadata found
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            match = cls.METADATA_PATTERN.search(content)
            if match:
                metadata_str = match.group(1)
                # Clean up the JSON string (remove leading * and whitespace from each line)
                cleaned = re.sub(r"\n\s*\*\s*", "\n", metadata_str)
                return json.loads(cleaned)

            return None

        except (IOError, json.JSONDecodeError, UnicodeDecodeError) as e:
            # Note: In production, use proper logging instead of print
            print(f"Error reading metadata from {file_path}: {e}")
            return None

    @classmethod
    def write_metadata(
        cls, file_path: str, metadata: Dict[str, Any], preserve_existing: bool = True
    ) -> bool:
        """
        Write or update metadata in a code file.

        Args:
            file_path: Path to the code file (.vue, .js, .ts)
            metadata: Dictionary of metadata to write
            preserve_existing: If True, merge with existing metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # If preserving, merge with existing metadata
            if preserve_existing:
                existing = cls.read_metadata(file_path)
                if existing:
                    # Merge: new metadata takes precedence
                    merged = {**existing, **metadata}
                    metadata = merged

            # Format metadata as JSDoc comment
            metadata_comment = cls._format_metadata_comment(metadata)

            # Check if metadata block already exists
            if cls.METADATA_PATTERN.search(content):
                # Replace existing metadata
                new_content = cls.METADATA_PATTERN.sub(metadata_comment, content)
            else:
                # Insert at the top of the file
                new_content = metadata_comment + "\n" + content

            # Write back to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return True

        except (IOError, json.JSONDecodeError, UnicodeDecodeError) as e:
            # Note: In production, use proper logging instead of print
            print(f"Error writing metadata to {file_path}: {e}")
            return False

    @classmethod
    def merge_metadata(cls, file_path: str, new_metadata: Dict[str, Any]) -> bool:
        """
        Merge new metadata with existing metadata in a code file.

        This is the recommended method for agents to update metadata,
        as it preserves all existing fields.

        Args:
            file_path: Path to the code file
            new_metadata: New metadata fields to add/update

        Returns:
            True if successful, False otherwise
        """
        return cls.write_metadata(file_path, new_metadata, preserve_existing=True)

    @classmethod
    def _format_metadata_comment(cls, metadata: Dict[str, Any]) -> str:
        """
        Format metadata as a JSDoc comment block.

        Args:
            metadata: Metadata dictionary

        Returns:
            Formatted JSDoc comment string
        """
        # Format as pretty JSON
        json_str = json.dumps(metadata, indent=2, ensure_ascii=False)

        # Split into lines and add JSDoc formatting
        lines = json_str.split("\n")
        formatted_lines = ["/**", " * @metadata {"]

        # Add each line with proper indentation and *
        for i, line in enumerate(lines):
            if i == 0:  # Skip opening brace (already added)
                continue
            elif i == len(lines) - 1:  # Closing brace
                formatted_lines.append(" * }")
            else:
                formatted_lines.append(f" * {line}")

        formatted_lines.append(" */")

        return "\n".join(formatted_lines)

    @classmethod
    def has_metadata(cls, file_path: str) -> bool:
        """
        Check if a file has metadata.

        Args:
            file_path: Path to the code file

        Returns:
            True if metadata exists, False otherwise
        """
        return cls.read_metadata(file_path) is not None

    @classmethod
    def get_files_without_metadata(
        cls,
        directory: str,
        extensions: List[str] = [".vue", ".js", ".ts"],
        exclude_patterns: List[str] = None,
    ) -> List[str]:
        """
        Find all code files in a directory without metadata.

        Args:
            directory: Directory to scan
            extensions: File extensions to check
            exclude_patterns: Patterns to exclude (e.g., 'node_modules', 'dist')

        Returns:
            List of file paths without metadata
        """
        if exclude_patterns is None:
            exclude_patterns = [
                "node_modules",
                "dist",
                "build",
                "deprecated",
                "__tests__",
            ]

        files_without_metadata = []
        path = Path(directory)

        for ext in extensions:
            for file_path in path.rglob(f"*{ext}"):
                # Skip excluded patterns
                if any(pattern in str(file_path) for pattern in exclude_patterns):
                    continue

                if not cls.has_metadata(str(file_path)):
                    files_without_metadata.append(str(file_path))

        return files_without_metadata


# Convenience functions for common operations
def mark_as_processed(
    file_path: str,
    agent_name: str,
    themes: List[str] = None,
    modules: List[str] = None,
    additional_metadata: Dict[str, Any] = None,
) -> bool:
    """
    Mark a file as processed by an agent.

    Args:
        file_path: Path to the code file
        agent_name: Name of the agent processing the file
        themes: List of themes/topics
        modules: List of modules affected
        additional_metadata: Any additional metadata fields

    Returns:
        True if successful, False otherwise
    """
    from datetime import date

    metadata = {
        "processed": True,
        "processed_date": date.today().isoformat(),
        "processed_by": agent_name,
    }

    if themes:
        metadata["themes"] = themes

    if modules:
        metadata["modules"] = modules

    if additional_metadata:
        metadata.update(additional_metadata)

    return CodeMetadataManager.merge_metadata(file_path, metadata)


def get_unprocessed_files(
    directory: str, extensions: List[str] = [".vue", ".js", ".ts"]
) -> List[str]:
    """
    Get list of unprocessed files in a directory.

    Args:
        directory: Directory to scan
        extensions: File extensions to check

    Returns:
        List of unprocessed file paths
    """
    return CodeMetadataManager.get_files_without_metadata(directory, extensions)
