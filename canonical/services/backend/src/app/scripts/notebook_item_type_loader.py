"""
Helper functions for loading NotebookItemType definitions from JSON files.

This module provides utilities to load and process NotebookItemType definitions
from the canonical artifacts directory structure.

Technical naming: All functions and variables in English (Rule 4.3).
"""

import json
import logging
from pathlib import Path
from typing import List

from app.database import db
from app.models import NotebookItemType

logger = logging.getLogger(__name__)


async def load_notebook_item_types_from_directory(
    directory: Path,
) -> List[NotebookItemType]:
    """
    Helper function to load NotebookItemType instances from a directory.

    Args:
        directory: Path to directory containing NotebookItemType JSON files

    Returns:
        List of created/existing NotebookItemType instances
    """
    notebook_item_types_created = []

    if not directory.exists():
        logger.warning("Directory not found: %s", directory)
        return []

    # Load each JSON file
    for json_file in directory.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                spec = json.load(f)

            # Check if the NotebookItemType with this ID already exists
            existing_type = None
            if "id" in spec and spec["id"]:
                existing_type = await db.find_one(
                    "notebook_item_types",
                    spec["id"],
                    NotebookItemType,
                    is_canonical=True,
                )

            if existing_type:
                logger.debug(
                    "NotebookItemType '%s' already exists: %s (skipping re-save)",
                    spec.get('name', spec.get('descricao')), existing_type.id
                )
                # NOTE: We skip db.insert() here to avoid modifying the JSON files on disk
                # The JSON files are the source-of-truth and should only be modified by git
                # Adding timestamps (created_at, updated_at) would cause them to be rewritten every startup
                notebook_item_types_created.append(existing_type)
            else:
                # Create NotebookItemType from spec
                notebook_item_type = create_notebook_item_type_from_spec(spec)
                await db.insert(
                    "notebook_item_types", notebook_item_type, current_user=SYSTEM_USER
                )
                logger.info("NotebookItemType '%s' created: %s", notebook_item_type.name, notebook_item_type.id)
                notebook_item_types_created.append(notebook_item_type)

        except Exception as e:
            logger.error("Error processing NotebookItemType '%s': %s", json_file.name, e)
            import traceback

            logger.error(traceback.format_exc())

    return notebook_item_types_created


def create_notebook_item_type_from_spec(spec: dict) -> NotebookItemType:
    """
    Create a NotebookItemType instance from a JSON specification.

    Handles both new structured format (with default_refs and default_initial_data)
    and legacy format (with python_refs, workflows, etc.), automatically converting
    legacy format to the new structure.

    Args:
        spec: Dictionary loaded from JSON file

    Returns:
        NotebookItemType instance
    """
    # Map spec to NotebookItemType fields
    notebook_item_type_data = {
        "id": spec.get("id"),
        "name": spec.get("name", spec.get("descricao", "Type Without Name")),
        "description": spec.get("description", spec.get("descricao", "")),
        "default_refs": spec.get("default_refs", {}),
        "default_initial_data": spec.get("default_initial_data", {}),
        "allow_instance_override_refs": spec.get("allow_instance_override_refs", True),
    }

    # Only do complex mapping if we're loading from legacy format
    # For new structured format, trust the JSON structure directly
    if "default_refs" not in spec or "default_initial_data" not in spec:
        # Build default_refs from spec references (legacy format)
        default_refs = {}

        # Map python_refs - look for workflow graph references
        if spec.get("python_refs"):
            python_refs = spec["python_refs"]
            # Find workflow graph references
            workflow_refs = [
                ref
                for ref in python_refs
                if "workflow" in ref.lower() or "graph" in ref.lower()
            ]
            if workflow_refs:
                default_refs["workflow_graph"] = workflow_refs
            # Store all python refs
            default_refs["python"] = python_refs

        # Handle workflows field (YAML or dict)
        if spec.get("workflows"):
            workflows = spec["workflows"]
            if isinstance(workflows, str) and workflows.strip():
                # YAML string workflow - store as reference
                import yaml

                try:
                    workflow_dict = yaml.safe_load(workflows)
                    if workflow_dict:
                        # Store structured workflow in default_initial_data
                        if "workflow_graph" not in default_refs:
                            default_refs["workflow_graph"] = []
                        # Store the YAML workflow structure in default_initial_data
                        notebook_item_type_data["default_initial_data"][
                            "workflow_yaml"
                        ] = workflows
                except Exception as yaml_err:
                    logger.warning("Failed to parse workflow YAML for %s: %s", spec.get('id'), yaml_err)
            elif isinstance(workflows, dict):
                # Structured workflow dict
                if "main_workflow" in workflows:
                    # Already has main_workflow structure
                    notebook_item_type_data["default_initial_data"]["workflow_dict"] = (
                        workflows
                    )
                else:
                    # Wrap in main_workflow structure
                    notebook_item_type_data["default_initial_data"]["workflow_dict"] = {
                        "main_workflow": workflows
                    }

        # Map other reference fields
        if spec.get("docs_refs"):
            default_refs["docs"] = spec["docs_refs"]

        if spec.get("javascript_refs"):
            default_refs["javascript"] = spec["javascript_refs"]

        if spec.get("yaml_refs"):
            default_refs["yaml"] = spec["yaml_refs"]

        if spec.get("attachment_refs"):
            default_refs["attachments"] = spec["attachment_refs"]

        notebook_item_type_data["default_refs"] = default_refs

        # Map other fields to default_initial_data
        initial_data = notebook_item_type_data["default_initial_data"]

        if spec.get("category"):
            initial_data["category"] = spec["category"]

        if spec.get("icon"):
            initial_data["icon"] = spec["icon"]

        if spec.get("properties"):
            initial_data["properties"] = spec["properties"]

        if spec.get("views_components"):
            initial_data["views_components"] = spec["views_components"]

        if spec.get("versao"):
            initial_data["versao"] = spec["versao"]

    # Create new NotebookItemType
    return NotebookItemType(**notebook_item_type_data)
