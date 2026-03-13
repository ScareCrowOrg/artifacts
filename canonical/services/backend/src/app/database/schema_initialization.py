"""
Schema initialization for application startup.

This module generates SCHEMAS.json from Pydantic models during application startup,
implementing the "Pydantic as Source of Truth" pattern for unified schema management.

Responsibilities:
- Generate SCHEMAS.json from Pydantic models (Phase 7 SchemaGenerator)
- Validate against existing schemas for divergence detection
- Log warnings if Pydantic models changed
- Update artifacts/canonical/SCHEMAS.json with generated schema
- Provide graceful fallback to static SCHEMAS.json on failure

Integration Point:
    main.py lifespan() → generate_and_validate_schemas() → CanonicalQueryEngine

Usage:
    from app.database.schema_initialization import generate_and_validate_schemas
    from app.config import ARTIFACTS_DIR

    schemas = generate_and_validate_schemas(ARTIFACTS_DIR / "canonical")
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def generate_and_validate_schemas(
    base_path: Path, save_to_disk: bool = True, validate_only: bool = False
) -> Dict[str, Any]:
    """
    Generate schemas from Pydantic models and validate against existing SCHEMAS.json.

    This function is called during application startup to ensure schemas are
    auto-generated from Pydantic models (Phase 7) and validated for divergence.

    Args:
        base_path: Path to canonical artifacts directory (e.g., artifacts/canonical)
        save_to_disk: If True, save generated schemas to SCHEMAS.json
        validate_only: If True, only validate without saving (dry-run mode)

    Returns:
        Generated schema dictionary ready for CanonicalQueryEngine

    Raises:
        Exception: If schema generation fails and fallback is needed

    Logging:
        - DEBUG: New fields detected in Pydantic models
        - WARNING: Type changes detected (potential breaking change)
        - INFO: Schema generation status and statistics
        - ERROR: Critical failures requiring fallback

    Examples:
        # Standard usage during startup
        schemas = generate_and_validate_schemas(ARTIFACTS_DIR / "canonical")

        # Dry-run validation only
        schemas = generate_and_validate_schemas(
            ARTIFACTS_DIR / "canonical",
            save_to_disk=False,
            validate_only=True
        )
    """
    logger.info("=" * 80)
    logger.info("SCHEMA GENERATION & VALIDATION")
    logger.info("=" * 80)
    logger.debug("Base path: %s", base_path)

    schemas_path = base_path / "SCHEMAS.json"

    # Import all 11 Pydantic models
    # Import inside function to avoid circular imports at module load time
    try:
        logger.debug("Importing Pydantic models...")
        from app.core.models import NotebookItem
        from app.models.ai_models import AIModel
        from app.models.content import Book, Cell, NotebookItemType
        from app.models.content_types import Content, ContentType
        from app.models.permissions import Permission, Role
        from app.models.templates import Template, Workflow

        logger.debug("✓ All Pydantic models imported successfully")
    except Exception as e:
        logger.error("✗ Failed to import Pydantic models: %s", e, exc_info=True)
        raise

    # Define model mapping (11 canonical collections)
    model_mapping: Dict[str, Type[BaseModel]] = {
        "permissions": Permission,
        "cells": Cell,
        "books": Book,
        "ai_models": AIModel,
        "content_types": ContentType,
        "notebook_items": NotebookItem,
        "templates": Template,
        "roles": Role,
        "workflows": Workflow,
        "notebook_item_types": NotebookItemType,
        "contents": Content,
    }

    logger.info("Generating schemas for %s collections...", len(model_mapping))

    # Import and use SchemaGenerator
    try:
        from app.database.schema_generator import SchemaGenerator

        generator = SchemaGenerator()
        generated_schemas = generator.generate_all_schemas(model_mapping)

        logger.info(
            f"✓ Schema generation complete: {len(generated_schemas) - 3} collections "
            "(excluding version/description/last_updated)"
        )
    except Exception as e:
        logger.error("✗ Schema generation failed: %s", e, exc_info=True)
        raise

    # Load existing SCHEMAS.json for comparison
    existing_schemas: Optional[Dict] = None
    if schemas_path.exists():
        try:
            logger.debug("Loading existing schemas from: %s", schemas_path)
            with open(schemas_path, "r") as f:
                existing_schemas = json.load(f)
            logger.debug("✓ Loaded existing schemas")
        except Exception as e:
            logger.warning("Failed to load existing SCHEMAS.json for comparison: %s", e)
            # Not critical - continue with new schemas
    else:
        logger.info("No existing SCHEMAS.json found at: %s", schemas_path)
        logger.info("This is normal for first-time initialization")

    # Compare and log divergence
    if existing_schemas:
        _log_schema_divergence(generated_schemas, existing_schemas)

    # Save to disk if requested and not in validate-only mode
    if save_to_disk and not validate_only:
        try:
            logger.info("Saving generated schemas to: %s", schemas_path)

            # Create backup of existing file
            if schemas_path.exists():
                backup_path = schemas_path.with_suffix(".json.backup")
                logger.debug("Creating backup: %s", backup_path)
                with open(schemas_path, "r") as f_src:
                    with open(backup_path, "w") as f_dst:
                        f_dst.write(f_src.read())

            # Save new schemas
            with open(schemas_path, "w") as f:
                json.dump(generated_schemas, f, indent=2)
                f.write("\n")  # Add trailing newline

            logger.info("✓ Schemas saved successfully")
        except Exception as e:
            logger.error("✗ Failed to save schemas: %s", e, exc_info=True)
            logger.warning("Continuing with in-memory schemas (not persisted)")

    logger.info("=" * 80)
    return generated_schemas


def _log_schema_divergence(generated: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """
    Compare generated and existing schemas, logging any divergence.

    Divergence Levels:
        - DEBUG: New fields added (non-breaking)
        - INFO: New collections added
        - WARNING: Type changes (potentially breaking)
        - WARNING: Missing fields (potential data loss)

    Args:
        generated: Newly generated schema dictionary
        existing: Existing schema dictionary from SCHEMAS.json
    """
    logger.debug("Comparing generated schemas with existing SCHEMAS.json...")

    # Metadata fields to exclude from comparison
    metadata_fields = {"version", "description", "last_updated"}

    # Get collection names
    generated_collections = set(generated.keys()) - metadata_fields
    existing_collections = set(existing.keys()) - metadata_fields

    # Check for missing collections
    missing_collections = existing_collections - generated_collections
    if missing_collections:
        logger.warning("Collections missing in generated schemas: %s", missing_collections)
        logger.warning(
            "These collections may need Pydantic models or were removed intentionally"
        )

    # Check for new collections
    new_collections = generated_collections - existing_collections
    if new_collections:
        logger.info("New collections in generated schemas: %s", new_collections)

    # Validate each common collection
    divergence_detected = False
    for collection in sorted(generated_collections & existing_collections):
        gen_schema = generated[collection]
        exist_schema = existing[collection]

        # Get field names
        gen_fields = set(gen_schema.keys())
        exist_fields = set(exist_schema.keys())

        # Check for missing fields (WARNING - potential data loss)
        missing_fields = exist_fields - gen_fields
        if missing_fields:
            logger.warning("[%s] Fields missing in generated schema: %s", collection, sorted(missing_fields))
            logger.warning(
                "[%s] These fields may have been removed from Pydantic model or need to be added back",
                collection
            )
            divergence_detected = True

        # Check for new fields (DEBUG - non-breaking)
        new_fields = gen_fields - exist_fields
        if new_fields:
            logger.debug("[%s] New fields in generated schema: %s", collection, sorted(new_fields))

        # Check for type changes (WARNING - potentially breaking)
        for field in sorted(gen_fields & exist_fields):
            gen_type = gen_schema[field].get("type")
            exist_type = exist_schema[field].get("type")

            if gen_type != exist_type:
                logger.warning("[%s.%s] Type changed: %s → %s", collection, field, exist_type, gen_type)
                logger.warning(
                    "[%s.%s] Verify Pydantic model change is intentional and doesn't break existing data",
                    collection, field
                )
                divergence_detected = True

    if not divergence_detected:
        logger.debug("✓ No schema divergence detected")
    else:
        logger.warning("")
        logger.warning("=" * 80)
        logger.warning("SCHEMA DIVERGENCE DETECTED")
        logger.warning("=" * 80)
        logger.warning("Pydantic models have diverged from existing SCHEMAS.json")
        logger.warning("Review warnings above and verify changes are intentional")
        logger.warning("")
        logger.warning("To regenerate schemas manually:")
        logger.warning("  python scripts/generate_canonical_schemas.py")
        logger.warning("=" * 80)


__all__ = ["generate_and_validate_schemas"]
