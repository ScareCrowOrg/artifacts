"""
State management module for orchestrator.

This module handles:
- Cell state updates in the database
- Publishing state change events
- Extracting outputs from workflow states
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.auth_legacy import SYSTEM_USER
from app.database import db
from app.event_bus import publish_cell_state_changed_sync
from app.models import Cell, CellStatus

logger = logging.getLogger(__name__)


class StateManager:
    """Manages cell state transitions and updates."""

    async def update_cell_state(
        self,
        cell_id: str,
        new_state: CellStatus,
        output_data: Optional[Dict[str, Any]] = None,
        error_data: Optional[str] = None,
    ) -> bool:
        """
        Update cell state in the database.

        Args:
            cell_id: ID of the cell to update
            new_state: New state for the cell
            output_data: Optional output data to merge into cell.data
            error_data: Optional error message

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            updates = {"estado": new_state.value, "dataAtualizacao": datetime.utcnow()}

            # Update output data if provided
            if output_data:
                cell = await db.find_one(
                    "cells", cell_id, current_user=SYSTEM_USER, model_class=Cell
                )
                if cell:
                    # Merge output_data into existing cell.initial_data
                    updated_data = {**cell.initial_data, **output_data}
                    updates["data"] = updated_data

            # Add error data if provided
            if error_data:
                updates["error_data"] = error_data

            await db.update("cells", cell_id, updates, current_user=SYSTEM_USER)
            logger.info("Cell %s state updated to: %s", cell_id, new_state.value)

            # Publish state change event
            try:
                cell = await db.find_one(
                    "cells", cell_id, current_user=SYSTEM_USER, model_class=Cell
                )
                cell_data = cell.model_dump() if cell else None
                publish_cell_state_changed_sync(cell_id, new_state.value, cell_data)
            except Exception as e:
                logger.warning("Failed to publish state change event: %s", e)

            return True

        except Exception as e:
            logger.error("Error updating cell %s: %s", cell_id, e)
            return False

    async def extract_outputs_from_state(
        self, final_state: Dict[str, Any], cell_id: str
    ) -> Dict[str, Any]:
        """
        Extract output data from custom graph final state.

        Args:
            final_state: Final state from workflow execution
            cell_id: ID of the cell being processed

        Returns:
            Dictionary of extracted output data
        """
        output_data = {}

        # Extract fragments if available
        if "fragments" in final_state:
            cell = await db.find_one(
                "cells", cell_id, current_user=SYSTEM_USER, model_class=Cell
            )
            if cell:
                cell.fragments = final_state["fragments"]
                await db.update(
                    "cells",
                    cell_id,
                    {"fragments": cell.fragments},
                    current_user=SYSTEM_USER,
                )
                logger.info("Updated cell with %s fragments", len(cell.fragments))

        # Extract context if available
        if "context" in final_state:
            output_data["workflow_context"] = final_state["context"]

        # Extract any other outputs from the state
        for key, value in final_state.items():
            if key not in [
                "cell_id",
                "cell_data",
                "agent_data",
                "fragments",
                "context",
                "error",
                "completed",
            ]:
                output_data[key] = value

        return output_data
