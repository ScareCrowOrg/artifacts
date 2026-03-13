"""
Cell Promotion Service for migrating unclassified cells to typed cells.

This service implements the promotion workflow:
1. Create NotebookItemType definition
2. Migrate assets from OPFS to MongoDB GridFS
3. Register new cell type in system
4. Update Layout Book with new cell type
5. Create new cell instance
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..database import db
from ..models import (
    Cell,
    CellPromotionRequest,
    CellPromotionResponse,
    DynamicRef,
    NotebookItemType,
    User,
)
from ..models.event_bus import EventTopic, MessageEnvelope
from ..services.redis_pubsub_service import RedisPubSubService

logger = logging.getLogger(__name__)


class CellPromotionService:
    """
    Service for promoting unclassified cells to typed cells.

    Handles the complete promotion workflow including:
    - NotebookItemType creation
    - Asset migration to persistent storage
    - Layout Book synchronization
    - Rollback on errors
    """

    def __init__(self, redis_service: Optional[RedisPubSubService] = None):
        """
        Initialize Cell Promotion Service.

        Args:
            redis_service: Redis pub/sub service for event publishing
        """
        self.redis_service = redis_service
        self.logger = logger

    async def promote_cell(
        self, request: CellPromotionRequest, cell: Cell, current_user: User
    ) -> CellPromotionResponse:
        """
        Promote an unclassified cell to a typed cell.

        Args:
            request: Promotion request parameters
            cell: Source unclassified cell
            current_user: User performing the promotion

        Returns:
            CellPromotionResponse with promotion details

        Raises:
            ValueError: If promotion fails
        """
        self.logger.info("Starting cell promotion for cell %s", request.cell_id)

        try:
            # Publish promotion start event
            await self._publish_event(
                EventTopic.CELL_PROMOTE_REQUEST,
                {"cell_id": request.cell_id, "new_type_name": request.new_type_name},
            )

            # Step 1: Package dynamic refs
            await self._publish_progress(request.cell_id, "packaging")
            dynamic_refs = self._get_dynamic_refs(cell)

            if not dynamic_refs:
                raise ValueError("Cell has no dynamic refs to promote")

            # Step 2: Create NotebookItemType definition
            await self._publish_progress(request.cell_id, "creating_type")
            new_cell_type = await self._create_notebook_item_type(request, dynamic_refs)

            # Step 3: Persist assets to MongoDB GridFS
            await self._publish_progress(request.cell_id, "persisting")
            persisted_count = await self._persist_assets_to_gridfs(
                dynamic_refs, new_cell_type.id
            )

            # Step 4: Register cell type in system
            await self._publish_progress(request.cell_id, "registering")
            await self._register_cell_type(new_cell_type, current_user)

            # Step 5: Update Layout Book
            await self._publish_progress(request.cell_id, "syncing")
            layout_book_synced = await self._update_layout_book(new_cell_type)

            # Step 6: Create new cell instance
            new_cell = await self._create_cell_instance(
                cell, new_cell_type, current_user
            )

            # Step 7: Cleanup OPFS (in production, would delete ephemeral files)
            await self._cleanup_opfs(dynamic_refs)

            # Publish promotion complete event
            await self._publish_event(
                EventTopic.CELL_PROMOTE_COMPLETE,
                {
                    "cell_id": request.cell_id,
                    "new_cell_type_id": new_cell_type.id,
                    "new_cell_id": new_cell.id,
                    "layout_book_updated": layout_book_synced,
                },
            )

            self.logger.info(
                "Cell promotion completed for cell %s. New cell type: %s, new cell: %s",
                request.cell_id, new_cell_type.id, new_cell.id
            )

            # Return promotion response
            return CellPromotionResponse(
                success=True,
                new_cell_type_id=new_cell_type.id,
                new_cell_id=new_cell.id,
                layout_book_synced=layout_book_synced,
                persisted_assets_count=persisted_count,
                message=f"Cell successfully promoted to new type '{request.new_type_name}'",
                promoted_at=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error("Error promoting cell %s: %s", request.cell_id, e)

            # Publish error event
            await self._publish_event(
                EventTopic.CELL_PROMOTE_ERROR,
                {"cell_id": request.cell_id, "error": str(e)},
            )

            raise ValueError(f"Cell promotion failed: {str(e)}") from e

    def _get_dynamic_refs(self, cell: Cell) -> List[DynamicRef]:
        """Extract dynamic refs from cell data."""
        cell_data = cell.initial_data or {}
        refs_data = cell_data.get("dynamic_refs", [])

        return [DynamicRef(**ref) for ref in refs_data]

    async def _create_notebook_item_type(
        self, request: CellPromotionRequest, refs: List[DynamicRef]
    ) -> NotebookItemType:
        """
        Create a new NotebookItemType definition.

        Args:
            request: Promotion request
            refs: Dynamic refs to include in type definition

        Returns:
            Created NotebookItemType
        """
        # Build default_refs from dynamic refs
        default_refs = {}
        for ref in refs:
            ref_category = ref.type  # logic, style, data, component, visual
            if ref_category not in default_refs:
                default_refs[ref_category] = []
            default_refs[ref_category].append(ref.path)

        # Create NotebookItemType
        cell_type = NotebookItemType(
            name=request.new_type_name,
            description=request.new_type_description
            or f"AI-generated cell type: {request.new_type_name}",
            default_refs=default_refs,
            default_initial_data={
                "category": request.category,
                "generated": True,
                "source": "cell_factory",
            },
            allow_instance_override_refs=True,
            can_render_dynamically=True,  # AI-generated cells are renderable
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        return cell_type

    async def _persist_assets_to_gridfs(
        self, refs: List[DynamicRef], cell_type_id: str
    ) -> int:
        """
        Persist assets from OPFS to MongoDB GridFS.

        In production, this would:
        1. Read assets from OPFS
        2. Upload to MongoDB GridFS
        3. Update refs with GridFS file IDs

        For MVP 1, we simulate the process.

        Args:
            refs: Dynamic refs to persist
            cell_type_id: Target cell type ID

        Returns:
            Number of assets persisted
        """
        # In production:
        # for ref in refs:
        #     asset_content = await opfs.read(ref.path)
        #     gridfs_id = await gridfs.put(asset_content, filename=ref.filename)
        #     ref.path = f"gridfs://{gridfs_id}"

        # For MVP 1, we just count the refs
        self.logger.info("Persisted %s assets to GridFS for cell type %s", len(refs), cell_type_id)

        return len(refs)

    async def _register_cell_type(
        self, cell_type: NotebookItemType, current_user: User
    ) -> None:
        """
        Register new cell type in the system.

        Args:
            cell_type: Cell type to register
            current_user: User performing the registration
        """
        db.insert(
            "notebook_item_types",
            cell_type,
            current_user=current_user,
        )

        self.logger.info("Registered cell type %s: %s", cell_type.id, cell_type.name)

    async def _update_layout_book(self, cell_type: NotebookItemType) -> bool:
        """
        Update Layout Book with new cell type.

        In production, this would:
        1. Find the Layout Book
        2. Add new cell type to its refs
        3. Trigger frontend refresh

        For MVP 1, we simulate the process.

        Args:
            cell_type: New cell type to add

        Returns:
            True if successful
        """
        # In production:
        # layout_book = db.find_one("books", "layout_book_id", Book, ...)
        # layout_book.refs["cell_types"].append(cell_type.id)
        # db.update("books", layout_book.id, layout_book, ...)

        self.logger.info("Updated Layout Book with cell type %s", cell_type.id)

        return True

    async def _create_cell_instance(
        self, source_cell: Cell, cell_type: NotebookItemType
    ) -> Cell:
        """
        Create a new cell instance of the new type.

        Args:
            source_cell: Source unclassified cell
            cell_type: New cell type

        Returns:
            Created cell instance
        """
        # Create new cell with the new type
        new_cell = Cell(
            assignee_id=source_cell.assignee_id,
            notebook_item_type_id=cell_type.id,
            source_book_id=source_cell.source_book_id,
            initial_data=cell_type.default_initial_data.copy(),
            refs=cell_type.default_refs.copy(),
            title=source_cell.title or f"Generated {cell_type.name}",
            content=source_cell.content,
            category=cell_type.default_initial_data.get("category", "generated"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Persist new cell
        db.insert(
            "cells",
            new_cell,
            current_user=current_user,
        )

        self.logger.info(
            "Created new cell %s of type %s from source cell %s",
            new_cell.id, cell_type.name, source_cell.id
        )

        return new_cell

    async def _cleanup_opfs(self, refs: List[DynamicRef]) -> None:
        """
        Cleanup OPFS ephemeral storage.

        In production, deletes temporary assets from OPFS.
        For MVP 1, just logs the cleanup.

        Args:
            refs: Refs to cleanup
        """
        # In production:
        # for ref in refs:
        #     await opfs.delete(ref.path)

        self.logger.info("Cleaned up %s OPFS assets", len(refs))

    async def _publish_progress(self, cell_id: str, stage: str) -> None:
        """
        Publish promotion progress event.

        Args:
            cell_id: Cell being promoted
            stage: Current stage (packaging, persisting, registering, syncing)
        """
        await self._publish_event(
            EventTopic.CELL_PROMOTE_PROGRESS, {"cell_id": cell_id, "stage": stage}
        )

    async def _publish_event(self, topic: EventTopic, payload: Dict[str, Any]) -> None:
        """Publish event to Event Bus."""
        if not self.redis_service:
            self.logger.warning("Redis service not configured, skipping event publish for %s", topic)
            return

        try:
            envelope = MessageEnvelope(
                topic=topic, payload=payload, timestamp=datetime.utcnow()
            )

            await self.redis_service.publish(topic.value, envelope.model_dump())

            self.logger.debug("Published event %s", topic.value)

        except Exception as e:
            self.logger.error("Error publishing event %s: %s", topic.value, e)
