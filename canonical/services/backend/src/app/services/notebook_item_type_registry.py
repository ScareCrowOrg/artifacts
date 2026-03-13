"""
NotebookItemType Registry Service.

This service provides dynamic discovery and loading of cell types from
the artifacts/canonical/cell_types/ directory.
"""

import os
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path

from ..models.content import NotebookItemType
from .resource_loader import get_resource_loader

logger = logging.getLogger(__name__)


class NotebookItemTypeRegistry:
    """Registry for dynamically loading and managing cell types."""

    def __init__(self, base_path: str = "artifacts/canonical/cell_types"):
        """
        Initialize the registry.

        Args:
            base_path: Path to cell types directory (relative to project root)
        """
        self.base_path = Path(base_path)
        self.types: Dict[str, NotebookItemType] = {}
        self._initialized = False

    async def discover_types(self, sync_to_db: bool = True) -> List[NotebookItemType]:
        """
        Scan base_path and load all type.json files.

        Args:
            sync_to_db: If True, automatically sync discovered types to database

        Returns:
            List of discovered NotebookItemType instances

        Raises:
            FileNotFoundError: If base_path doesn't exist
            json.JSONDecodeError: If type.json is invalid
        """
        if not self.base_path.exists():
            raise FileNotFoundError(f"Cell types directory not found: {self.base_path}")

        discovered_types = []

        # Scan for directories containing type.json
        for type_dir in self.base_path.iterdir():
            if not type_dir.is_dir():
                continue

            type_json_path = type_dir / "type.json"
            if type_json_path.exists():
                try:
                    cell_type = self._load_type(type_json_path)
                    self.types[cell_type.id] = cell_type
                    discovered_types.append(cell_type)
                except Exception as e:
                    # Log error but continue discovering other types
                    logger.warning("Error loading type from %s: %s", type_json_path, e, exc_info=True)

        self._initialized = True

        # Automatically sync to database if requested
        if sync_to_db and discovered_types:
            try:
                synced_count = await self.sync_to_database(discovered_types)
                logger.info("Synced %s/%s types to database", synced_count, len(discovered_types))
            except Exception as e:
                logger.error("Error syncing types to database: %s", e, exc_info=True)

        return discovered_types

    def discover_types_sync(self) -> List[NotebookItemType]:
        """
        Synchronous version of discover_types for backward compatibility.

        Note: This version does NOT sync to database. Use discover_types()
        (async) for automatic database synchronization.

        Returns:
            List of discovered NotebookItemType instances
        """
        if not self.base_path.exists():
            raise FileNotFoundError(f"Cell types directory not found: {self.base_path}")

        discovered_types = []

        # Scan for directories containing type.json
        for type_dir in self.base_path.iterdir():
            if not type_dir.is_dir():
                continue

            type_json_path = type_dir / "type.json"
            if type_json_path.exists():
                try:
                    cell_type = self._load_type(type_json_path)
                    self.types[cell_type.id] = cell_type
                    discovered_types.append(cell_type)
                except Exception as e:
                    # Log error but continue discovering other types
                    logger.warning("Error loading type from %s: %s", type_json_path, e, exc_info=True)

        self._initialized = True
        return discovered_types

    def _load_type(self, path: Path) -> NotebookItemType:
        """
        Load and validate type.json.

        Args:
            path: Path to type.json file

        Returns:
            Validated NotebookItemType instance

        Raises:
            json.JSONDecodeError: If JSON is invalid
            ValueError: If type data is invalid
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate required fields
        if "id" not in data:
            raise ValueError(f"Missing 'id' field in {path}")
        if "name" not in data:
            raise ValueError(f"Missing 'name' field in {path}")

        # Create NotebookItemType instance (Pydantic will validate)
        return NotebookItemType(**data)

    async def sync_to_database(self, types: List[NotebookItemType]) -> int:
        """
        Sync discovered cell types to the database.

        This makes cell types available via the standard API endpoints
        that query the database (e.g., /api/cells/types/list).

        Args:
            types: List of NotebookItemType instances to sync

        Returns:
            Number of types successfully synced

        Note:
            This is idempotent - if a type already exists in the database,
            it will be updated with the latest definition from the registry.
        """
        from ..database import db

        synced_count = 0

        for cell_type in types:
            try:
                # Check if type already exists
                existing = await db.find_one(
                    "notebook_item_types", cell_type.id, NotebookItemType, is_canonical=True
                )

                if existing:
                    # Update existing type with latest definition
                    await db.update(
                        "notebook_item_types", cell_type.id, cell_type, is_canonical=True
                    )
                    logger.debug("Updated cell type in database: %s", cell_type.id)
                else:
                    # Insert new type
                    await db.insert("notebook_item_types", cell_type, current_user=SYSTEM_USER)
                    logger.debug("Inserted cell type into database: %s", cell_type.id)

                synced_count += 1

            except Exception as e:
                logger.error("Error syncing type '%s' to database: %s", cell_type.id, e, exc_info=True)

        return synced_count

    def get_type(self, type_id: str) -> Optional[NotebookItemType]:
        """
        Get type by ID.

        Args:
            type_id: ID of the cell type

        Returns:
            NotebookItemType instance or None if not found
        """
        if not self._initialized:
            self.discover_types_sync()

        return self.types.get(type_id)

    def list_types(self) -> List[NotebookItemType]:
        """
        Get all registered types.

        Returns:
            List of all NotebookItemType instances
        """
        if not self._initialized:
            self.discover_types_sync()

        return list(self.types.values())

    def resolve_ref_path(self, type_id: str, ref_key: str, ref_path: str) -> Optional[Path]:
        """
        Resolve relative ref path to absolute path.

        Args:
            type_id: ID of the cell type
            ref_key: Reference key (e.g., 'scripts', 'view')
            ref_path: Relative path from type.json

        Returns:
            Absolute Path object or None if type not found

        Example:
            >>> registry.resolve_ref_path(
            ...     "example",
            ...     "scripts",
            ...     "backend/scripts/main.py"
            ... )
            Path('/path/to/artifacts/canonical/cell_types/example/backend/scripts/main.py')
        """
        cell_type = self.get_type(type_id)
        if not cell_type:
            return None

        type_dir = self.base_path / type_id
        return type_dir / ref_path

    def validate_refs(self, type_id: str) -> Dict[str, bool]:
        """
        Validate that all referenced files exist.

        Args:
            type_id: ID of the cell type

        Returns:
            Dict mapping ref paths to existence status
        """
        cell_type = self.get_type(type_id)
        if not cell_type:
            return {}

        validation_results = {}

        for ref_key, ref_paths in cell_type.default_refs.items():
            for ref_path in ref_paths:
                absolute_path = self.resolve_ref_path(type_id, ref_key, ref_path)
                validation_results[ref_path] = absolute_path.exists() if absolute_path else False

        return validation_results

    def stage_cell_type_resources(self, type_id: str) -> Dict[str, List[Path]]:
        """
        Stage all resources for a cell type using ResourceLoader.

        This provides unified access to both local and remote resources,
        staging them in a temporary cache area for consistent execution.

        Args:
            type_id: ID of the cell type

        Returns:
            Dict mapping ref types to staged resource paths

        Example:
            >>> registry = NotebookItemTypeRegistry()
            >>> staged = registry.stage_cell_type_resources("example")
            >>> print(staged["scripts"])
            [Path("/tmp/scareverse/cell_resources/example/backend/scripts/main.py")]
        """
        cell_type = self.get_type(type_id)
        if not cell_type:
            raise ValueError(f"Cell type '{type_id}' not found")

        # Get the resource loader
        resource_loader = get_resource_loader()

        # Determine base path for local files
        base_local_path = self.base_path / type_id

        # Stage all resources
        staged_refs = resource_loader.stage_cell_type(
            cell_type_id=type_id, refs=cell_type.default_refs, base_local_path=base_local_path
        )

        logger.info("Staged %s resource types for cell type '%s'", len(staged_refs), type_id)
        return staged_refs


# Global registry instance (initialized at app startup)
_registry: Optional[NotebookItemTypeRegistry] = None


def get_registry() -> NotebookItemTypeRegistry:
    """
    Get the global registry instance.

    Returns:
        Global NotebookItemTypeRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = NotebookItemTypeRegistry()
    return _registry
