"""
System API Router - RESTful endpoints for ScareVerse system utilities.

Implements status, seed data, and development endpoints.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.audit_logger import log_audit_event
from app.auth_legacy import get_current_user_required
from app.core.redis_client import invalidate_all_cache
from app.database import db
from app.models import Book, Cell, NotebookItemType, User
from app.permissions import require_admin
from app.scripts.seed_data import init_seed_data

logger = logging.getLogger(__name__)

# Create system router
system_router = APIRouter(tags=["Sistema"])


@system_router.get("/status")
async def status_sistema(current_user: User = Depends(get_current_user_required)):
    """
    Status geral do sistema.

    Required: authenticated user
    """
    try:
        try:
            users = await db.find_many(
                "users", current_user=current_user, model_class=User
            )
            celulas = await db.find_many(
                "cells", current_user=current_user, model_class=Cell
            )
            livros = await db.find_many(
                "books", current_user=current_user, model_class=Book
            )
            notebook_item_types = await db.find_many(
                "notebook_item_types",
                current_user=current_user,
                model_class=NotebookItemType,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        return {
            "status": "operational",
            "version": "1.0.0",
            "statistics": {
                "users": len(users),
                "cells": len(celulas),
                "books": len(livros),
                "notebook_item_types": len(notebook_item_types),
            },
        }
    except Exception as e:
        logger.error("Erro ao obter status: %s", e)
        return {"status": "error", "error": "Erro interno ao obter status do sistema"}


@system_router.post("/seed-data")
async def seed_system_data(current_user: User = Depends(require_admin)):
    """
    Inicializar dados de seed do sistema.

    Cria tipos de célula padrão e outros dados iniciais necessários.
    Requer permissão de administrador.
    """
    try:
        result = await init_seed_data()
        logger.info("Seed data initialized by admin user %s", current_user.id)
        return {
            "success": True,
            "message": "Dados de seed inicializados com sucesso",
            "data": result,
        }
    except Exception as e:
        logger.error("Erro ao inicializar seed data: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao inicializar seed data: {str(e)}",
        )


@system_router.post("/cache/invalidate")
async def invalidate_cache(
    request: Request, current_user: User = Depends(require_admin)
):
    """
    Invalidate all Redis cache globally.

    This endpoint flushes all keys from the Redis cache database.
    Use with caution as it will clear all cached data and may temporarily
    impact system performance until the cache is repopulated.

    Requires administrator permissions.

    Returns:
        dict: Result containing success status and number of keys deleted
    """
    try:
        # Get client IP for audit logging
        ip_address = request.client.host if request and request.client else "unknown"

        logger.info("Cache invalidation requested by admin user %s from %s", current_user.id, ip_address)

        # Perform cache invalidation
        result = await invalidate_all_cache()

        # Log audit event
        log_audit_event(
            user_id=current_user.id,
            action="cache.invalidate_all",
            resource_type="system",
            resource_id="redis_cache",
            details={
                "keys_deleted": result.get("keys_deleted", 0),
                "success": result.get("success", False),
                "ip_address": ip_address,
            },
            ip_address=ip_address,
        )

        if result.get("success"):
            logger.info(
                "Cache invalidation successful. User: %s, Keys deleted: %s",
                current_user.id, result.get('keys_deleted', 0)
            )
            return {
                "success": True,
                "message": result.get("message"),
                "keys_deleted": result.get("keys_deleted", 0),
            }
        else:
            logger.warning("Cache invalidation failed: %s", result.get('message'))
            return {
                "success": False,
                "message": result.get("message"),
                "keys_deleted": 0,
            }

    except Exception as e:
        error_msg = str(e)
        logger.error("Error in cache invalidation endpoint: %s", error_msg)

        # Log failed attempt
        log_audit_event(
            user_id=current_user.id,
            action="cache.invalidate_all",
            resource_type="system",
            resource_id="redis_cache",
            details={
                "error": error_msg,
                "success": False,
                "ip_address": ip_address if "ip_address" in locals() else "unknown",
            },
            ip_address=ip_address if "ip_address" in locals() else "unknown",
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao invalidar cache: {error_msg}",
        )
