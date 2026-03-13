"""
Audit Logs API Router - RESTful endpoints for audit log access.

Provides admin-only access to audit logs with filtering and statistics.
Implements comprehensive audit trail visibility for security monitoring.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..config.database import RUNTIME_DIR
from ..models.users import User
from ..permissions import require_admin

logger = logging.getLogger(__name__)

# Create audit logs router
audit_router = APIRouter(prefix="/audit", tags=["Audit"])


@audit_router.get("/logs")
async def get_audit_logs(
    event_type: Optional[str] = Query(
        None,
        description="Filter by event type (permission_denied, role_assigned, role_removed, admin_action)",
    ),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    start_date: Optional[str] = Query(
        None, description="Start date in ISO format (e.g., 2025-01-01T00:00:00)"
    ),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    _current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Lista audit logs (somente admin).

    Permite filtrar por tipo de evento, usuário, e range de datas.
    Retorna logs em ordem decrescente de timestamp.

    Filtros disponíveis:
    - event_type: permission_denied, role_assigned, role_removed, admin_action
    - user_id: ID do usuário
    - start_date/end_date: Range de datas (ISO format)
    - skip/limit: Paginação

    Permissão requerida: admin
    """
    try:
        # Build filters
        filters = {}

        if event_type:
            filters["event_type"] = event_type
        if user_id:
            filters["user_id"] = user_id

        # Note: Date filtering would need custom implementation in JSONDatabase
        # For now, we'll retrieve all matching logs and filter in memory

        # Get all audit logs from runtime storage
        # Since we're using JSONDatabase, we need to read files directly
        import json

        audit_logs_dir = RUNTIME_DIR / "audit_logs"
        logs = []

        if audit_logs_dir.exists():
            for log_file in audit_logs_dir.glob("*.json"):
                try:
                    with open(log_file, "r") as f:
                        log_data = json.load(f)

                    # Apply filters
                    if event_type and log_data.get("event_type") != event_type:
                        continue
                    if user_id and log_data.get("user_id") != user_id:
                        continue

                    # Date filtering
                    if start_date or end_date:
                        log_timestamp = log_data.get("timestamp")
                        if log_timestamp:
                            if start_date and log_timestamp < start_date:
                                continue
                            if end_date and log_timestamp > end_date:
                                continue

                    logs.append(log_data)

                except Exception as e:
                    logger.warning("Failed to read audit log file %s: %s", log_file, e)
                    continue

        # Sort by timestamp descending
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Apply pagination
        total_count = len(logs)
        paginated_logs = logs[skip : skip + limit]

        logger.info("Retrieved %s audit logs (total: %s)", len(paginated_logs), total_count)

        return {
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "logs": paginated_logs,
        }

    except Exception as e:
        logger.error("Erro ao buscar audit logs: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar audit logs: {str(e)}",
        )


@audit_router.get("/stats")
async def get_audit_stats(
    _current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Estatísticas de audit logs (somente admin).

    Retorna contadores e top 10 de permissões negadas.

    Permissão requerida: admin
    """
    try:
        import json
        from collections import Counter

        audit_logs_dir = RUNTIME_DIR / "audit_logs"

        # Initialize counters
        permission_denied_count = 0
        role_changes_count = 0
        admin_actions_count = 0
        denied_permissions = []

        if audit_logs_dir.exists():
            for log_file in audit_logs_dir.glob("*.json"):
                try:
                    with open(log_file, "r") as f:
                        log_data = json.load(f)

                    event_type = log_data.get("event_type")

                    if event_type == "permission_denied":
                        permission_denied_count += 1
                        # Extract required permission for stats
                        details = log_data.get("details", {})
                        req_perm = details.get("required_permission")
                        if req_perm:
                            denied_permissions.append(req_perm)

                    elif event_type in ["role_assigned", "role_removed"]:
                        role_changes_count += 1

                    elif event_type == "admin_action":
                        admin_actions_count += 1

                except Exception as e:
                    logger.warning("Failed to read audit log file %s: %s", log_file, e)
                    continue

        # Calculate top denied permissions
        permission_counter = Counter(denied_permissions)
        top_denied_permissions = [
            {"permission": perm, "count": count}
            for perm, count in permission_counter.most_common(10)
        ]

        stats = {
            "permission_denied_count": permission_denied_count,
            "role_changes_count": role_changes_count,
            "admin_actions_count": admin_actions_count,
            "top_denied_permissions": top_denied_permissions,
        }

        logger.info("Retrieved audit statistics")
        return stats

    except Exception as e:
        logger.error("Erro ao calcular estatísticas de audit: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao calcular estatísticas: {str(e)}",
        )
