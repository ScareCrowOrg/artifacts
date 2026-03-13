"""
Roles API Router - RESTful endpoints for ScareVerse role management.

Implements CRUD endpoints for roles and user role assignment.
Admin-only operations for managing RBAC roles and permissions.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..audit_logger import log_role_assigned, log_role_removed
from ..auth import get_current_user_required
from ..database import db
from ..models.permissions import Permission, Role, RoleEnum
from ..models.users import User
from ..permissions import invalidate_user_cache, require_admin

logger = logging.getLogger(__name__)

# Create roles router
roles_router = APIRouter(prefix="/roles", tags=["Roles"])


@roles_router.get("/", response_model=List[Role])
async def list_roles(current_user: User = Depends(get_current_user_required)):
    """
    Lista todos os roles disponíveis.

    Autenticação requerida (qualquer usuário pode ver roles).
    """
    try:
        try:
            roles = await db.find_many(
                "roles", current_user=current_user, model_class=Role
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        logger.info("Listados %s roles", len(roles))
        return roles

    except Exception as e:
        logger.error("Erro ao listar roles: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar roles: {str(e)}",
        )


@roles_router.get("/{role_name}", response_model=Role)
async def get_role(
    role_name: str, current_user: User = Depends(get_current_user_required)
):
    """
    Obtém detalhes de um role específico.

    Autenticação requerida.
    """
    try:
        try:
            roles = await db.find(
                "roles",
                {"name": role_name},
                current_user=current_user,
            )
            role = roles[0] if roles else None
            if role and isinstance(role, dict):
                role = Role(**role)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_name}' não encontrado",
            )

        return role

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao obter role: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter role: {str(e)}",
        )


@roles_router.post("/", response_model=Role, status_code=status.HTTP_201_CREATED)
async def create_role(role: Role, current_user: User = Depends(require_admin)):
    """
    Cria novo role (somente admin).

    Permissão requerida: admin
    """
    try:
        # Validate that role doesn't exist
        try:
            roles = await db.find(
                "roles",
                {"name": role.name},
                current_user=current_user,
            )
            existing = roles[0] if roles else None
            if existing and isinstance(existing, dict):
                existing = Role(**existing)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{role.name}' já existe",
            )

        # Create role
        role_dict = role.model_dump()
        doc_id = await db.insert("roles", role_dict, current_user=current_user)
        created = await db.find_one(
            "roles", doc_id, current_user=current_user, model_class=Role
        )

        logger.info("Role '%s' criado por admin %s", role.name, current_user.id)
        return created

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao criar role: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar role: {str(e)}",
        )


@roles_router.put("/{role_id}", response_model=Role)
async def update_role(
    role_id: str, role_update: dict, current_user: User = Depends(require_admin)
):
    """
    Atualiza role existente (somente admin).

    Permissão requerida: admin
    """
    try:
        try:
            role = await db.find_one(
                "roles", role_id, current_user=current_user, model_class=Role
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role não encontrado"
            )

        # Update role
        success = await db.update(
            "roles", role_id, role_update, current_user=current_user
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha ao atualizar role",
            )

        # Invalidate cache for all users with this role
        # Note: This is a simple approach. In production, you might want to track users by role
        logger.info("Role '%s' atualizado por admin %s", role.name, current_user.id)

        return await db.find_one(
            "roles", role_id, current_user=current_user, model_class=Role
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao atualizar role: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar role: {str(e)}",
        )


@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: str, current_user: User = Depends(require_admin)):
    """
    Deleta role (somente admin).

    Permissão requerida: admin

    ATENÇÃO: Não deletar roles padrão (admin, user, viewer, guest).
    """
    try:
        try:
            role = await db.find_one(
                "roles", role_id, current_user=current_user, model_class=Role
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role não encontrado"
            )

        # Protect default roles
        if role.name in [
            RoleEnum.ADMIN,
            RoleEnum.USER,
            RoleEnum.VIEWER,
            RoleEnum.GUEST,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é permitido deletar role padrão '{role.name}'",
            )

        # Delete role
        success = await db.delete("roles", role_id, current_user=current_user)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha ao deletar role",
            )

        logger.info("Role '%s' deletado por admin %s", role.name, current_user.id)
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao deletar role: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar role: {str(e)}",
        )


@roles_router.put("/users/{user_id}/roles", response_model=User)
async def assign_role_to_user(
    user_id: str,
    request: Request,
    role_name: str = Query(..., description="Nome do role a ser atribuído"),
    current_user: User = Depends(require_admin),
):
    """
    Atribui role a um usuário (somente admin).

    Permissão requerida: admin

    Query parameter:
    - role_name: Nome do role a ser atribuído
    """
    try:
        # Validate that role exists
        try:
            roles = await db.find(
                "roles",
                {"name": role_name},
                current_user=current_user,
            )
            role = roles[0] if roles else None
            if role and isinstance(role, dict):
                role = Role(**role)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_name}' não encontrado",
            )

        # Validate that user exists
        try:
            user = await db.find_one(
                "users", user_id, current_user=current_user, model_class=User
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado"
            )

        # Add role if not already assigned
        if role_name not in user.roles:
            user.roles.append(role_name)
            await db.update(
                "users",
                user_id,
                {"roles": user.roles},
                current_user=current_user,
            )

            # Invalidate user's permissions cache
            invalidate_user_cache(user_id)

            # Audit log the role assignment
            ip_address = request.client.host if request and request.client else None
            log_role_assigned(
                admin_id=current_user.id,
                user_id=user_id,
                role_name=role_name,
                ip_address=ip_address,
            )

            logger.info("Role '%s' atribuído ao usuário %s por admin %s", role_name, user_id, current_user.id)

        return await db.find_one(
            "users", user_id, current_user=current_user, model_class=User
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao atribuir role: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atribuir role: {str(e)}",
        )


@roles_router.delete("/users/{user_id}/roles/{role_name}", response_model=User)
async def remove_role_from_user(
    user_id: str,
    role_name: str,
    request: Request,
    current_user: User = Depends(require_admin),
):
    """
    Remove role de um usuário (somente admin).

    Permissão requerida: admin
    """
    try:
        try:
            user = await db.find_one(
                "users", user_id, current_user=current_user, model_class=User
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado"
            )

        # Remove role if present
        if role_name in user.roles:
            user.roles.remove(role_name)
            await db.update(
                "users",
                user_id,
                {"roles": user.roles},
                current_user=current_user,
            )

            # Invalidate user's permissions cache
            invalidate_user_cache(user_id)

            # Audit log the role removal
            ip_address = request.client.host if request and request.client else None
            log_role_removed(
                admin_id=current_user.id,
                user_id=user_id,
                role_name=role_name,
                ip_address=ip_address,
            )

            logger.info("Role '%s' removido do usuário %s por admin %s", role_name, user_id, current_user.id)

        return await db.find_one(
            "users", user_id, current_user=current_user, model_class=User
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao remover role: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao remover role: {str(e)}",
        )


@roles_router.get("/permissions/", response_model=List[Permission])
async def list_permissions(current_user: User = Depends(get_current_user_required)):
    """
    Lista todas as permissões disponíveis.

    Autenticação requerida (informativo para todos os usuários).
    """
    try:
        try:
            permissions = await db.find_many(
                "permissions", current_user=current_user, model_class=Permission
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        logger.info("Listadas %s permissões", len(permissions))
        return permissions

    except Exception as e:
        logger.error("Erro ao listar permissões: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar permissões: {str(e)}",
        )
