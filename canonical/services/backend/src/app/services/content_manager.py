"""
ContentManager service for managing typed content assets.

This service provides:
- ContentType loading and validation from canonical JSON files
- Content CRUD operations with MongoDB persistence
- Storage abstraction (local/cloud/repo)
- Version management and lineage tracking
- Schema validation against ContentType definitions
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..database import db
from ..models import User
from ..models.content_types import (
    Content,
    ContentQueryFilters,
    ContentType,
    CreateContentRequest,
    UpdateContentMetadataRequest,
)

logger = logging.getLogger(__name__)


class ContentTypeLoader:
    """
    Loads and caches ContentType definitions from Git.

    ContentTypes are stored as JSON files in artifacts/canonical/content_types/
    and loaded on-demand with caching for performance.
    """

    def __init__(self, content_types_dir: str = None):
        """
        Initialize ContentType loader.

        Args:
            content_types_dir: Path to content_types directory
                              (defaults to artifacts/canonical/content_types/)
        """
        if content_types_dir is None:
            # Default to canonical content_types directory
            from ..config import BASE_DIR

            content_types_dir = BASE_DIR / "artifacts" / "canonical" / "content_types"

        self.content_types_dir = Path(content_types_dir)
        self._cache: Dict[str, ContentType] = {}
        logger.info("ContentTypeLoader initialized with dir: %s", self.content_types_dir)

    def load_content_type(self, content_type_id: str) -> Optional[ContentType]:
        """
        Load a ContentType by ID.

        Args:
            content_type_id: ContentType identifier (e.g., 'image-png')

        Returns:
            ContentType instance or None if not found

        Raises:
            ValueError: If ContentType JSON is invalid
        """
        # Check cache first
        if content_type_id in self._cache:
            return self._cache[content_type_id]

        # Try to find the file
        json_path = self.content_types_dir / f"{content_type_id}.json"

        if not json_path.exists():
            logger.warning("ContentType not found: %s at %s", content_type_id, json_path)
            return None

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            content_type = ContentType(**data)

            # Validate that the ID matches
            if content_type.id != content_type_id:
                raise ValueError(
                    f"ContentType ID mismatch: file name '{content_type_id}' "
                    f"vs JSON id '{content_type.id}'"
                )

            # Cache and return
            self._cache[content_type_id] = content_type
            logger.info("Loaded ContentType: %s", content_type_id)
            return content_type

        except Exception as e:
            logger.error("Error loading ContentType %s: %s", content_type_id, e)
            raise ValueError(f"Invalid ContentType definition: {e}") from e

    def list_content_types(self) -> List[ContentType]:
        """
        List all available ContentTypes.

        Returns:
            List of all ContentType instances
        """
        content_types = []

        if not self.content_types_dir.exists():
            logger.warning("ContentTypes directory not found: %s", self.content_types_dir)
            return content_types

        for json_file in self.content_types_dir.glob("*.json"):
            if json_file.stem == "README":
                continue

            try:
                content_type = self.load_content_type(json_file.stem)
                if content_type:
                    content_types.append(content_type)
            except Exception as e:
                logger.error("Error loading ContentType from %s: %s", json_file, e)

        return content_types

    def reload_cache(self):
        """Clear cache and reload all ContentTypes."""
        self._cache.clear()
        logger.info("ContentType cache cleared")


class ContentManager:
    """
    Manages Content instances with ContentType validation.

    Provides:
    - Content creation with ContentType schema validation
    - Version management (immutable content with version tracking)
    - Storage abstraction (local/cloud/repo)
    - Query and retrieval operations
    - Lineage tracking via origin_cell_id
    """

    def __init__(self, content_type_loader: ContentTypeLoader = None):
        """
        Initialize ContentManager.

        Args:
            content_type_loader: ContentTypeLoader instance (creates default if None)
        """
        self.loader = content_type_loader or ContentTypeLoader()
        logger.info("ContentManager initialized")

    def validate_content_fragments(
        self, content_type: ContentType, fragments: Dict[str, Any]
    ) -> bool:
        """
        Validate content fragments against ContentType schema.

        Args:
            content_type: ContentType definition
            fragments: Content metadata to validate

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """
        expected = content_type.expected_fragments

        # Simple validation: check required keys (list format)
        if isinstance(expected, list):
            missing = [key for key in expected if key not in fragments]
            if missing:
                raise ValueError(
                    f"Missing required fragments for ContentType '{content_type.id}': {missing}"
                )
            return True

        # Advanced validation: JSON Schema format (dict)
        if isinstance(expected, dict):
            for key, schema in expected.items():
                # Skip optional fields
                if isinstance(schema, dict) and schema.get("optional", False):
                    continue

                # Check required field presence
                if key not in fragments:
                    raise ValueError(
                        f"Missing required fragment '{key}' for ContentType '{content_type.id}'"
                    )

                # Basic type validation
                if isinstance(schema, dict) and "type" in schema:
                    expected_type = schema["type"]
                    actual_value = fragments[key]

                    # Map JSON schema types to Python types
                    type_map = {
                        "string": str,
                        "integer": int,
                        "number": (int, float),
                        "boolean": bool,
                        "object": dict,
                        "array": list,
                    }

                    if expected_type in type_map:
                        py_type = type_map[expected_type]
                        if not isinstance(actual_value, py_type):
                            raise ValueError(
                                f"Fragment '{key}' has wrong type. "
                                f"Expected {expected_type}, got {type(actual_value).__name__}"
                            )

        return True

    async def create_content(
        self, request: CreateContentRequest, current_user: User
    ) -> Content:
        """
        Create new content with ContentType validation.

        Args:
            request: Content creation request
            current_user: User creating the content

        Returns:
            Created Content instance

        Raises:
            ValueError: If validation fails or ContentType not found
        """
        # Load and validate ContentType
        content_type = self.loader.load_content_type(request.content_type_id)
        if not content_type:
            raise ValueError(f"ContentType not found: {request.content_type_id}")

        # Validate fragments against ContentType schema
        self.validate_content_fragments(content_type, request.fragments)

        # Create Content instance
        content = Content(
            content_type_id=request.content_type_id,
            assignee_id=request.assignee_id,
            data_ref=request.data_ref,
            origin_cell_id=request.origin_cell_id,
            fragments=request.fragments,
            filename=request.filename,
            size_bytes=request.size_bytes,
            checksum=request.checksum,
            tags=request.tags,
            metadata=request.metadata,
        )

        # Persist to MongoDB
        await db.insert("contents", content, current_user=current_user)

        logger.info("Created content: %s (type: %s)", content.id, content.content_type_id)
        return content

    def get_content(self, content_id: str) -> Optional[Content]:
        """
        Retrieve content by ID.

        Args:
            content_id: Content UUID

        Returns:
            Content instance or None if not found
        """
        content_dict = db.find_one("contents", {"id": content_id})
        if not content_dict:
            return None

        return Content(**content_dict)

    async def query_contents(self, filters: ContentQueryFilters) -> List[Content]:
        """
        Query contents with filters.

        Args:
            filters: Query filters

        Returns:
            List of matching Content instances
        """
        query = {}

        if filters.content_type_id:
            query["content_type_id"] = filters.content_type_id

        if filters.assignee_id:
            query["assignee_id"] = filters.assignee_id

        if filters.origin_cell_id:
            query["origin_cell_id"] = filters.origin_cell_id

        if filters.is_latest is not None:
            query["is_latest"] = filters.is_latest

        if filters.tags:
            query["tags"] = {"$all": filters.tags}

        results = await db.find("contents", query)
        return [Content(**item) for item in results]

    async def create_new_version(
        self,
        previous_content_id: str,
        request: UpdateContentMetadataRequest,
        current_user: User,
    ) -> Content:
        """
        Create a new version of existing content.

        This implements immutable versioning: instead of updating the existing
        content, we create a new version and mark the old one as not latest.

        Args:
            previous_content_id: UUID of previous version
            request: Updated metadata
            current_user: User creating the new version

        Returns:
            New Content version

        Raises:
            ValueError: If previous content not found
        """
        # Get previous version
        previous = self.get_content(previous_content_id)
        if not previous:
            raise ValueError(f"Content not found: {previous_content_id}")

        # Mark previous version as not latest
        await db.update(
            "contents", {"id": previous_content_id}, {"$set": {"is_latest": False}}
        )

        # Create new version
        new_version = Content(
            content_type_id=previous.content_type_id,
            assignee_id=previous.assignee_id,
            data_ref=previous.data_ref,
            version=previous.version + 1,
            is_latest=True,
            previous_version_id=previous_content_id,
            origin_cell_id=previous.origin_cell_id,
            fragments=request.fragments or previous.fragments,
            filename=previous.filename,
            size_bytes=previous.size_bytes,
            checksum=previous.checksum,
            tags=request.tags or previous.tags,
            metadata=request.metadata or previous.metadata,
        )

        # Validate new fragments if changed
        if request.fragments:
            content_type = self.loader.load_content_type(new_version.content_type_id)
            if content_type:
                self.validate_content_fragments(content_type, new_version.fragments)

        # Persist to MongoDB
        await db.insert("contents", new_version, current_user=current_user)

        logger.info(
            "Created new version: %s v%s (previous: %s)",
            new_version.id, new_version.version, previous_content_id
        )
        return new_version

    async def get_content_history(self, content_id: str) -> List[Content]:
        """
        Get version history for content.

        Args:
            content_id: UUID of any version in the chain

        Returns:
            List of all versions, ordered from oldest to newest
        """
        # Get the current content
        current = self.get_content(content_id)
        if not current:
            return []

        # Build version chain backwards
        versions = [current]
        prev_id = current.previous_version_id

        while prev_id:
            prev = self.get_content(prev_id)
            if not prev:
                break
            versions.insert(0, prev)
            prev_id = prev.previous_version_id

        # Find any newer versions
        query = {"previous_version_id": content_id}
        newer = await db.find("contents", query)
        for item in newer:
            versions.append(Content(**item))

        return versions
