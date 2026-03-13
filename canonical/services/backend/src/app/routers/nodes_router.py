"""
Platform Node API Router.

Implements endpoints for registering, listing, updating heartbeats, and deregistering
platform nodes (Runners, Workers, Launchers, GateKeepers).

Each node is uniquely identified by (user_id, node_nickname). Two different users
may have nodes with the same nickname, but a single user cannot register two nodes
with the same nickname.
"""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user_required
from ..database import db
from ..models import (
    NodeSummary,
    PlatformNode,
    RegisterNodeRequest,
    User,
)

logger = logging.getLogger(__name__)

nodes_router = APIRouter(prefix="/nodes", tags=["Platform Nodes"])


@nodes_router.post("", response_model=NodeSummary, status_code=status.HTTP_201_CREATED)
async def register_node(
    request: RegisterNodeRequest,
    current_user: User = Depends(get_current_user_required),
):
    """
    Register a new platform node.

    Requires authentication via a valid PAT or session token.

    node_nickname must be:
    - Unique within the user's account (UNIQUE per user_id)
    - Lowercase alphanumeric + hyphens only (^[a-z0-9-]+$)
    - Maximum 64 characters
    """
    # Enforce uniqueness: (user_id, node_nickname)
    # NOTE: db.find_many validates collection access but does NOT filter by user_id.
    # The manual filter below is intentional — it ensures we only check the current
    # user's nodes for nickname uniqueness (per-user, not global uniqueness).
    try:
        existing_nodes = await db.find_many(
            "platform_nodes",
            current_user=current_user,
            model_class=PlatformNode,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error checking existing nodes: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error registering node",
        ) from exc

    user_nodes = [n for n in existing_nodes if n.user_id == current_user.id]
    for node in user_nodes:
        if node.is_active and node.node_nickname == request.node_nickname:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Node nickname '{request.node_nickname}' is already registered "
                    "for your account. Use a different nickname or deregister the existing node."
                ),
            )

    new_node = PlatformNode(
        user_id=current_user.id,
        node_nickname=request.node_nickname,
        node_type=request.node_type,
        endpoint_url=request.endpoint_url,
        platform_info=request.platform_info,
    )

    try:
        await db.insert(
            "platform_nodes",
            new_node,
            current_user=current_user,
        )
    except Exception as exc:
        logger.error("Failed to persist platform node: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register node",
        ) from exc

    logger.info(
        "Node '%s' (%s) registered for user %s",
        request.node_nickname,
        request.node_type,
        current_user.id,
    )

    return NodeSummary(
        id=new_node.id,
        node_nickname=new_node.node_nickname,
        node_type=new_node.node_type,
        endpoint_url=new_node.endpoint_url,
        platform_info=new_node.platform_info,
        registered_at=new_node.registered_at,
        last_heartbeat=new_node.last_heartbeat,
        is_active=new_node.is_active,
    )


@nodes_router.get("", response_model=List[NodeSummary])
async def list_nodes(
    current_user: User = Depends(get_current_user_required),
):
    """
    List all platform nodes belonging to the authenticated user.
    """
    try:
        # NOTE: db.find_many validates collection access but does NOT filter by user_id.
        # The manual filter below is intentional — it ensures only the current user's
        # nodes are returned.
        all_nodes = await db.find_many(
            "platform_nodes",
            current_user=current_user,
            model_class=PlatformNode,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error listing nodes: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing nodes",
        ) from exc

    user_nodes = [n for n in all_nodes if n.user_id == current_user.id]

    return [
        NodeSummary(
            id=n.id,
            node_nickname=n.node_nickname,
            node_type=n.node_type,
            endpoint_url=n.endpoint_url,
            platform_info=n.platform_info,
            registered_at=n.registered_at,
            last_heartbeat=n.last_heartbeat,
            is_active=n.is_active,
        )
        for n in user_nodes
    ]


@nodes_router.post("/{node_id}/heartbeat", response_model=NodeSummary)
async def node_heartbeat(
    node_id: str,
    current_user: User = Depends(get_current_user_required),
):
    """
    Update the last_heartbeat timestamp for a registered node.

    Called periodically by runners/workers to signal they are alive.
    """
    try:
        node = await db.find_one(
            "platform_nodes",
            node_id,
            current_user=current_user,
            model_class=PlatformNode,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error retrieving node %s: %s", node_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating heartbeat",
        ) from exc

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found",
        )

    if node.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update heartbeats for your own nodes",
        )

    if not node.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot send heartbeat for a deregistered node",
        )

    now = datetime.utcnow()

    try:
        await db.update(
            "platform_nodes",
            node_id,
            {"last_heartbeat": now},
            current_user=current_user,
        )
    except Exception as exc:
        logger.error("Error updating heartbeat for node %s: %s", node_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating heartbeat",
        ) from exc

    logger.debug("Heartbeat received for node %s (user %s)", node_id, current_user.id)

    return NodeSummary(
        id=node.id,
        node_nickname=node.node_nickname,
        node_type=node.node_type,
        endpoint_url=node.endpoint_url,
        platform_info=node.platform_info,
        registered_at=node.registered_at,
        last_heartbeat=now,
        is_active=node.is_active,
    )


@nodes_router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deregister_node(
    node_id: str,
    current_user: User = Depends(get_current_user_required),
):
    """
    Deregister (soft-delete) a platform node.

    Sets is_active=False. The node record is retained for audit purposes.
    """
    try:
        node = await db.find_one(
            "platform_nodes",
            node_id,
            current_user=current_user,
            model_class=PlatformNode,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error retrieving node %s for deregistration: %s", node_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deregistering node",
        ) from exc

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found",
        )

    if node.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only deregister your own nodes",
        )

    if not node.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Node is already deregistered",
        )

    try:
        await db.update(
            "platform_nodes",
            node_id,
            {"is_active": False},
            current_user=current_user,
        )
    except Exception as exc:
        logger.error("Error deregistering node %s: %s", node_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deregistering node",
        ) from exc

    logger.info("Node %s deregistered by user %s", node_id, current_user.id)
