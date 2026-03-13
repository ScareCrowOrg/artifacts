"""
Action Discovery Router

Provides REST API endpoints for discovering AgenteLab actions dynamically.

Endpoints:
- GET /api/actions/discovery - List all labels and actions
- GET /api/actions/discovery?label=<name> - Get actions by label
- GET /api/actions/discovery?label=<name>&action=<name> - Get action details
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user_required
from ..models.users import User
from ..services.action_discovery import get_discovery_service

logger = logging.getLogger(__name__)

# Create router
action_discovery_router = APIRouter(prefix="/actions", tags=["action-discovery"])


@action_discovery_router.get("/discovery")
async def discover_actions(
    label: Optional[str] = Query(
        None, description="Filter by label (e.g., 'search', 'file-operations')"
    ),
    action: Optional[str] = Query(
        None, description="Specific action name (requires label parameter)"
    ),
    _current_user: User = Depends(get_current_user_required),
) -> Dict[str, Any]:
    """
    Discover available AgenteLab actions dynamically.

    Required: authenticated user

    Three modes of operation:

    1. **List all labels and actions** (no parameters):
       - Returns: `{"labels": {"search": ["grep", "find"], ...}}`

    2. **Get actions by label** (label parameter only):
       - Returns: `{"label": "search", "actions": [{"name": "grep", "description": "...", "parameters": [...]}]}`

    3. **Get action details** (label + action parameters):
       - Returns: `{"action": {...complete action definition...}}`

    Examples:
        - `/api/actions/discovery` - List all
        - `/api/actions/discovery?label=search` - Search actions
        - `/api/actions/discovery?label=search&action=grep` - Grep details
    """
    try:
        discovery = get_discovery_service()

        # DEBUG LOG: Service state
        logger.info("[DISCOVERY] [DEBUG] Service state:")
        logger.info("[DISCOVERY] [DEBUG]   - actions_dir: %s", discovery.actions_dir)
        logger.info("[DISCOVERY] [DEBUG]   - actions_cache is None: %s", discovery._actions_cache is None)
        logger.info("[DISCOVERY] [DEBUG]   - labels_cache is None: %s", discovery._labels_cache is None)

        # Mode 1: List all labels and actions
        if label is None and action is None:
            logger.info("[DISCOVERY] Listing all labels and actions")

            # DEBUG LOG: Before discover_all
            logger.info("[DISCOVERY] [DEBUG] Calling discover_all()...")

            labels = discovery.discover_all()
            parse_errors = discovery.get_parse_errors()

            # DEBUG LOG: Results
            logger.info("[DISCOVERY] [DEBUG] discover_all() returned:")
            logger.info("[DISCOVERY] [DEBUG]   - Type: %s", type(labels))
            logger.info("[DISCOVERY] [DEBUG]   - Length: %s", len(labels))
            logger.info("[DISCOVERY] [DEBUG]   - Content: %s", labels)
            logger.info("[DISCOVERY] [DEBUG]   - Parse errors: %s", len(parse_errors))
            if parse_errors:
                logger.info("[DISCOVERY] [DEBUG]   - Errors detail: %s", parse_errors)

            response = {
                "status": "ok",
                "mode": "list_all",
                "labels": labels,
                "total_labels": len(labels),
                "total_actions": sum(len(actions) for actions in labels.values()),
            }

            # Include parse errors as warnings if any exist
            if parse_errors:
                response["warnings"] = parse_errors
                logger.warning("[DISCOVERY] Returning %s parse errors as warnings", len(parse_errors))

            # DEBUG LOG: Response being returned
            logger.info("[DISCOVERY] [DEBUG] Returning response: %s", response)

            return response

        # Mode 2: Get actions by label
        elif label is not None and action is None:
            logger.info("[DISCOVERY] Getting actions for label: %s", label)
            actions = discovery.discover_by_label(label)

            if not actions:
                raise HTTPException(status_code=404, detail=f"Label not found: {label}")

            return {
                "status": "ok",
                "mode": "filter_by_label",
                "label": label,
                "actions": actions,
                "count": len(actions),
            }

        # Mode 3: Get specific action details
        elif label is not None and action is not None:
            logger.info("[DISCOVERY] Getting action details: %s/%s", label, action)
            action_details = discovery.discover_action(label, action)

            if action_details is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Action not found: {action} in label {label}",
                )

            return {
                "status": "ok",
                "mode": "get_action_details",
                "action": action_details,
            }

        # Invalid combination (action without label)
        else:
            raise HTTPException(
                status_code=400, detail="Action parameter requires label parameter"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[DISCOVERY] Error: %s", e)
        raise HTTPException(status_code=500, detail=f"Discovery error: {str(e)}") from e


@action_discovery_router.post("/discovery/refresh")
async def refresh_discovery_cache(
    _current_user: User = Depends(get_current_user_required),
) -> Dict[str, str]:
    """
    Refresh the action discovery cache.

    Required: authenticated user

    Useful after adding or modifying action YAML files.

    Returns:
        Status message with parse errors if any
    """
    try:
        logger.info("[DISCOVERY] Refreshing cache")
        discovery = get_discovery_service()
        discovery.refresh_cache()

        # Get updated counts and parse errors
        labels = discovery.discover_all()
        parse_errors = discovery.get_parse_errors()

        response = {
            "status": "ok",
            "message": "Discovery cache refreshed successfully",
            "total_labels": len(labels),
            "total_actions": sum(len(actions) for actions in labels.values()),
        }

        # Include parse errors as warnings if any exist
        if parse_errors:
            response["warnings"] = parse_errors
            logger.warning("[DISCOVERY] Cache refresh found %s parse errors", len(parse_errors))

        return response
    except Exception as e:
        logger.error("[DISCOVERY] Error refreshing cache: %s", e)
        raise HTTPException(status_code=500, detail=f"Cache refresh error: {str(e)}") from e
