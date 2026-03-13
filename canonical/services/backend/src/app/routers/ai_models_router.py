"""
AI Models Router - Endpoints for managing AI models as artifacts.

This router implements CRUD endpoints for AI model management:
- GET /ai-models/list - List available models
- GET /ai-models/{id} - Get specific model
- POST /ai-models/create - Create new model
- PUT /ai-models/{id}/update - Update model
- POST /ai-models/{id}/activate - Activate/deactivate model
- DELETE /ai-models/{id}/delete - Delete model
"""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import get_current_user_required
from ..database import db
from ..models import AIModel, CreateAIModelRequest, UpdateAIModelRequest, User

logger = logging.getLogger(__name__)

# Create AI Models router
ai_models_router = APIRouter(prefix="/ai-models", tags=["AI Models"])


@ai_models_router.get("/list", response_model=List[AIModel])
async def list_ai_models(current_user: User = Depends(get_current_user_required)):
    """
    List all available AI models.

    Required: authenticated user

    Returns only active models by default. Use query parameter `all=true`
    to include inactive models.
    """
    try:
        # Get all AI models
        try:
            models = await db.find_many(
                "ai_models",
                current_user=current_user,
                model_class=AIModel,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        # Filter only active models
        active_models = [m for m in models if m.active]

        # Return as Pydantic models (FastAPI will serialize to JSON)
        return active_models

    except Exception as e:
        logger.error("Error listing AI models: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing models: {str(e)}",
        )


@ai_models_router.get("/{model_id}", response_model=AIModel)
async def get_ai_model(
    model_id: str, current_user: User = Depends(get_current_user_required)
):
    """
    Get details of a specific AI model.

    Required: authenticated user
    """
    try:
        try:
            model = await db.find_one(
                "ai_models",
                model_id,
                current_user=current_user,
                model_class=AIModel,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI model {model_id} not found",
            )

        return model

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting AI model: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting model: {str(e)}",
        )


@ai_models_router.post(
    "/create", response_model=AIModel, status_code=status.HTTP_201_CREATED
)
async def create_ai_model(
    request: CreateAIModelRequest,
    _scope: str = "published",  # Phase 1B: AI model definitions ALWAYS go to MongoDB (canonical)
    current_user: User = Depends(get_current_user_required),
):
    """
    Create a new AI model.

    **Phase 1B - Special Case**:
    - AI model definitions are ALWAYS stored in MongoDB (scope="published" is forced)
    - These are canonical system-wide resources, not user artifacts
    - Sandbox is not used for AI model definitions

    Requires authentication.

    Example request body:
    ```json
    {
        "name": "GPT-4",
        "description": "Advanced OpenAI model",
        "type": "cloud",
        "provider": "openai",
        "modelId": "gpt-4",
        "version": "1.0.0",
        "active": true,
        "configuration": {"temperature": 0.7},
        "metadata": {"context": "128K tokens"}
    }
    ```
    """
    try:
        # Check if model with same modelId and provider already exists
        try:
            results = await db.find(
                "ai_models",
                {"modelId": request.modelId, "provider": request.provider},
                current_user=current_user,
            )
            existing = results[0] if results else None
            if existing and isinstance(existing, dict):
                existing = AIModel(**existing)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Model {request.modelId} from provider {request.provider} already exists",
            )

        # Create new model
        # Phase 1B: AI model definitions ALWAYS go to MongoDB (canonical, not sandbox)
        model = AIModel(**request.model_dump())
        await db.insert("ai_models", model, current_user=current_user)

        logger.info("AI model '%s' created: %s (scope=published)", model.name, model.id)

        return model

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating AI model: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating model: {str(e)}",
        )


@ai_models_router.put("/{model_id}/update", response_model=AIModel)
async def update_ai_model(
    model_id: str,
    request: UpdateAIModelRequest,
    current_user: User = Depends(get_current_user_required),
):
    """
    Update an existing AI model.

    The model ID must be passed in the URL. If the 'id' field is included in
    the request body (as the frontend does), it will be automatically ignored
    by Pydantic v2, ensuring compatibility.

    Requires authentication.

    Example request body (the 'id' field is optional and will be ignored):
    ```json
    {
        "id": "50e9e4f0-bf4b-4231-83f9-1b22713a01e6",  // Ignored
        "name": "Gemini Pro",
        "description": "Cloud model",
        "type": "cloud",
        "provider": "gemini",
        "modelId": "gemini-pro",
        "version": "1.0.0",
        "active": true,
        "configuration": {"temperature": 0.7},
        "metadata": {"context": "32K tokens"}
    }
    ```
    """
    try:
        # Find the model
        try:
            model = await db.find_one(
                "ai_models",
                model_id,
                current_user=current_user,
                model_class=AIModel,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI model {model_id} not found",
            )

        # Prepare updates
        updates = {}

        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.type is not None:
            updates["type"] = request.type.value
        if request.provider is not None:
            updates["provider"] = request.provider
        if request.modelId is not None:
            updates["modelId"] = request.modelId
        if request.apiKey is not None:
            updates["apiKey"] = request.apiKey
        if request.version is not None:
            updates["version"] = request.version
        if request.active is not None:
            updates["active"] = request.active
        if request.configuration is not None:
            updates["configuration"] = request.configuration
        if request.metadata is not None:
            updates["metadata"] = request.metadata

        # Update timestamp
        updates["updatedAt"] = datetime.utcnow()

        # Update in database
        success = await db.update("ai_models", model_id, updates, is_canonical=True)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update model",
            )

        # Retrieve updated model
        try:
            updated_model = await db.find_one(
                "ai_models",
                model_id,
                current_user=current_user,
                model_class=AIModel,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        logger.info("AI model %s updated", model_id)

        return updated_model

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating AI model: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating model: {str(e)}",
        )


@ai_models_router.post("/{model_id}/activate", response_model=AIModel)
async def activate_ai_model(
    model_id: str,
    active: bool = Query(..., description="true to activate, false to deactivate"),
    current_user: User = Depends(get_current_user_required),
):
    """
    Activate or deactivate an AI model.

    Requires authentication.

    Query parameter:
    - active: boolean (true to activate, false to deactivate)
    """
    try:
        # Find the model
        try:
            model = await db.find_one(
                "ai_models",
                model_id,
                current_user=current_user,
                model_class=AIModel,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI model {model_id} not found",
            )

        # Update status
        updates = {"active": active, "updatedAt": datetime.utcnow()}

        success = await db.update("ai_models", model_id, updates, is_canonical=True)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update model status",
            )

        # Retrieve updated model
        try:
            updated_model = await db.find_one(
                "ai_models",
                model_id,
                current_user=current_user,
                model_class=AIModel,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        status_text = "activated" if active else "deactivated"
        logger.info("AI model %s %s", model_id, status_text)

        return updated_model

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error activating/deactivating AI model: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating status: {str(e)}",
        )


@ai_models_router.delete("/{model_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_model(
    model_id: str, current_user: User = Depends(get_current_user_required)
):
    """
    Delete an AI model.

    Requires authentication.

    WARNING: This operation is permanent and cannot be undone.
    """
    try:
        # Find the model
        try:
            model = await db.find_one(
                "ai_models",
                model_id,
                current_user=current_user,
                model_class=AIModel,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI model {model_id} not found",
            )

        # Delete from database
        success = await db.delete("ai_models", model_id, is_canonical=True)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete model",
            )

        logger.info("AI model %s deleted", model_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting AI model: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting model: {str(e)}",
        )
