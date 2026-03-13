"""
Config API Router - RESTful endpoints for ScareVerse configuration management.

Implements system configuration endpoints.

Note: OAuth configuration has been moved to CentralHub.
See centralhub/app/routers/config_router.py for OAuth endpoints.
"""

import logging
from typing import Any, Dict, List

import yaml
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user_required
from ..config import BASE_DIR
from ..models import User

logger = logging.getLogger(__name__)

# Create config router
config_router = APIRouter(prefix="/config", tags=["Configuração"])


@config_router.get("/agentlab/warm-up-files", response_model=List[Dict[str, Any]])
async def listar_warmup_files(_current_user: User = Depends(get_current_user_required)):
    """
    List available AgenteLab warm-up YAML configuration files.

    Required: authenticated user

    Returns a list of available YAML files in docs/official/agents/warm-up/ directory.
    Files can be selected in the ChatSettingsPanel to configure AgenteLab persona.
    """
    try:
        warmup_dir = BASE_DIR / "docs" / "official" / "agents" / "warm-up"

        if not warmup_dir.exists():
            logger.warning("Warm-up directory does not exist: %s", warmup_dir)
            return []

        files = []
        # Support both .yml and .yaml extensions
        for file_path in list(warmup_dir.glob("*.yml")) + list(
            warmup_dir.glob("*.yaml")
        ):
            if file_path.is_file():
                files.append(
                    {
                        "filename": file_path.name,
                        "path": str(file_path.relative_to(BASE_DIR)),
                        "size": file_path.stat().st_size,
                    }
                )

        # Sort by filename
        files.sort(key=lambda x: x["filename"])

        logger.info("Found %s warm-up files", len(files))
        return files

    except Exception as e:
        logger.error("Error listing warm-up files: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing warm-up files: {str(e)}",
        )


@config_router.get("/agentlab/personas", response_model=Dict[str, Any])
async def listar_personas(_current_user: User = Depends(get_current_user_required)):
    """
    List available AgenteLab personas with their associated files.

    Required: authenticated user

    Returns persona definitions from agentlab_personas.yml if available,
    otherwise returns a default structure.
    """
    try:
        personas_file = (
            BASE_DIR
            / "docs"
            / "official"
            / "agents"
            / "warm-up"
            / "agentlab_personas.yml"
        )

        if not personas_file.exists():
            logger.warning("Personas file does not exist: %s", personas_file)
            return {"personas": [], "message": "Personas configuration file not found"}

        # Check file size limit (prevent resource exhaustion)
        file_size = personas_file.stat().st_size
        MAX_FILE_SIZE = 1024 * 1024  # 1MB limit for YAML files
        if file_size > MAX_FILE_SIZE:
            logger.error("Personas file too large: %s bytes", file_size)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Personas configuration file exceeds size limit",
            )

        with open(personas_file, "r", encoding="utf-8") as f:
            # Use safe_load to prevent arbitrary code execution
            try:
                personas_config = yaml.safe_load(f)
            except yaml.YAMLError as ye:
                logger.error("Invalid YAML in personas file: %s", ye)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid YAML format in personas configuration",
                )

        # Validate the structure
        if not isinstance(personas_config, dict):
            logger.error("Personas file does not contain a valid dictionary")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid personas configuration structure",
            )

        return {
            "personas": personas_config.get("personas", []),
            "metadata": personas_config.get("metadata", {}),
            "selection_guidelines": personas_config.get("selection_guidelines", {}),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing personas: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing personas: {str(e)}",
        )


@config_router.get("/agentlab/action-files", response_model=List[Dict[str, Any]])
async def listar_action_files(_current_user: User = Depends(get_current_user_required)):
    """
    List available AgenteLab action link reference YAML files.

    Required: authenticated user

    Returns a list of available YAML files in docs/official/agents/actions/ directory.
    Files can be selected in the ChatSettingsPanel to provide quick action link reference.
    """
    try:
        actions_dir = BASE_DIR / "docs" / "official" / "agents" / "actions"

        if not actions_dir.exists():
            logger.warning("Actions directory does not exist: %s", actions_dir)
            return []

        files = []
        # Support both .yml and .yaml extensions
        for file_path in list(actions_dir.glob("*.yml")) + list(
            actions_dir.glob("*.yaml")
        ):
            if file_path.is_file():
                # Try to parse YAML to get metadata
                action_data = {}  # Initialize to avoid NameError in exception handler
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        action_data = yaml.safe_load(f)
                        metadata = (
                            action_data.get("metadata", {})
                            if isinstance(action_data, dict)
                            else {}
                        )
                except Exception as e:
                    logger.warning("Could not parse %s: %s", file_path.name, e)
                    metadata = {}

                files.append(
                    {
                        "filename": file_path.name,
                        "path": str(file_path.relative_to(BASE_DIR)),
                        "size": file_path.stat().st_size,
                        "action_name": metadata.get("action_name", file_path.stem),
                        "action_type": metadata.get("action_type", "unknown"),
                        "description": (
                            action_data.get("description", "").split("\n")[0]
                            if isinstance(action_data, dict)
                            else ""
                        ),
                    }
                )

        # Sort by action name
        files.sort(key=lambda x: x["action_name"])

        logger.info("Found %s action files", len(files))
        return files

    except Exception as e:
        logger.error("Error listing action files: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing action files: {str(e)}",
        )
