"""
Action Discovery Service

Provides plug-and-play discovery of AgenteLab actions by scanning and parsing
action YAML files from the documentation directory.

Features:
- Automatic discovery of available actions
- Label-based categorization
- Detailed action metadata retrieval
- Dynamic registry without manual registration
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from app.config import BASE_DIR

logger = logging.getLogger(__name__)


class ActionParameter(BaseModel):
    """Model for action parameter definition"""

    name: str
    type: str
    required: bool = False
    default: Optional[Any] = None
    description: Optional[str] = None


class ActionMetadata(BaseModel):
    """Model for action metadata from YAML files"""

    action_name: str
    action_type: str = "JSON"
    version: str = "1.0.0"
    date: Optional[str] = None
    status: str = "active"
    labels: List[str] = Field(default_factory=list)
    related_docs: List[str] = Field(default_factory=list)


class ActionDefinition(BaseModel):
    """Complete action definition"""

    name: str
    metadata: ActionMetadata
    description: str
    syntax: Optional[str] = None
    parameters: List[ActionParameter] = Field(default_factory=list)
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    best_practices: List[str] = Field(default_factory=list)
    tips: List[str] = Field(default_factory=list)


class ActionDiscoveryService:
    """
    Service for discovering and managing AgenteLab actions

    Scans action YAML files and provides:
    - List of all labels and actions
    - Actions filtered by label
    - Detailed action information
    """

    def __init__(self, actions_dir: Optional[Path] = None):
        """
        Initialize the discovery service

        Args:
            actions_dir: Path to actions YAML directory (default: auto-detect)
        """
        if actions_dir is None:
            # Use centralized BASE_DIR from config.py (RULESET.md Rule 4.1)
            actions_dir = BASE_DIR / "docs" / "official" / "agents" / "actions"

        self.actions_dir = Path(actions_dir)
        self._actions_cache: Optional[Dict[str, ActionDefinition]] = None
        self._labels_cache: Optional[Dict[str, List[str]]] = None
        self._parse_errors: List[
            Dict[str, str]
        ] = []  # Track files that failed to parse

        # DEBUG LOG: Detailed initialization info
        import os

        logger.info("[ACTION_DISCOVERY] [DEBUG] Initialization Details:")
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - BASE_DIR: %s", BASE_DIR)
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - Current working directory: %s", os.getcwd())
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - Resolved actions_dir: %s", self.actions_dir)
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - Absolute path: %s", self.actions_dir.absolute())
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - Directory exists: %s", self.actions_dir.exists())
        if self.actions_dir.exists():
            logger.info("[ACTION_DISCOVERY] [DEBUG]   - Directory is_dir: %s", self.actions_dir.is_dir())
            logger.info("[ACTION_DISCOVERY] [DEBUG]   - Directory readable: %s", os.access(self.actions_dir, os.R_OK))
        logger.info("[ACTION_DISCOVERY] Initialized with directory: %s", self.actions_dir)

    def _load_actions(self) -> Dict[str, ActionDefinition]:
        """
        Load and parse all action YAML files

        Returns:
            Dictionary mapping action names to ActionDefinition objects
        """
        # DEBUG LOG: Check if using cache
        if self._actions_cache is not None:
            logger.info("[ACTION_DISCOVERY] [DEBUG] Using cached actions: %s actions", len(self._actions_cache))
            return self._actions_cache

        logger.info("[ACTION_DISCOVERY] [DEBUG] Loading actions from disk (no cache)")

        actions = {}
        self._parse_errors = []  # Reset parse errors on reload

        # DEBUG LOG: Directory existence check
        logger.info("[ACTION_DISCOVERY] [DEBUG] Checking directory: %s", self.actions_dir)
        logger.info("[ACTION_DISCOVERY] [DEBUG] Directory exists: %s", self.actions_dir.exists())

        if not self.actions_dir.exists():
            logger.error("[ACTION_DISCOVERY] Actions directory not found: %s", self.actions_dir)
            logger.error("[ACTION_DISCOVERY] [DEBUG] Absolute path: %s", self.actions_dir.absolute())
            return actions

        # Find all YAML files
        yml_files = list(self.actions_dir.glob("*.yml"))
        yaml_files_ext = list(self.actions_dir.glob("*.yaml"))

        # DEBUG LOG: Glob results
        logger.info("[ACTION_DISCOVERY] [DEBUG] Glob results:")
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - *.yml files: %s", len(yml_files))
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - *.yaml files: %s", len(yaml_files_ext))
        if yml_files:
            logger.info("[ACTION_DISCOVERY] [DEBUG]   - yml files: %s", [f.name for f in yml_files])
        if yaml_files_ext:
            logger.info("[ACTION_DISCOVERY] [DEBUG]   - yaml files: %s", [f.name for f in yaml_files_ext])

        yaml_files = yml_files + yaml_files_ext

        # Skip README files
        original_count = len(yaml_files)
        yaml_files = [f for f in yaml_files if f.stem.lower() != "readme"]
        filtered_count = original_count - len(yaml_files)

        # DEBUG LOG: Filtering results
        if filtered_count > 0:
            logger.info("[ACTION_DISCOVERY] [DEBUG] Filtered out %s README files", filtered_count)

        logger.info("[ACTION_DISCOVERY] Found %s action files", len(yaml_files))

        # DEBUG LOG: Process each file
        for yaml_file in yaml_files:
            logger.info("[ACTION_DISCOVERY] [DEBUG] Processing file: %s", yaml_file.name)
            try:
                action_def = self._parse_action_file(yaml_file)
                if action_def:
                    actions[action_def.name] = action_def
                    logger.info("[ACTION_DISCOVERY] [DEBUG] ✓ Successfully loaded action: %s", action_def.name)
                else:
                    logger.warning("[ACTION_DISCOVERY] [DEBUG] ✗ Parse returned None for: %s", yaml_file.name)
            except Exception as e:
                error_msg = str(e)
                logger.error("[ACTION_DISCOVERY] [DEBUG] ✗ Exception parsing %s: %s", yaml_file.name, error_msg)
                logger.warning("[ACTION_DISCOVERY] Failed to parse %s: %s", yaml_file.name, error_msg)
                self._parse_errors.append({"file": yaml_file.name, "error": error_msg})

        self._actions_cache = actions

        # DEBUG LOG: Final results
        logger.info("[ACTION_DISCOVERY] [DEBUG] Load complete:")
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - Successful: %s actions", len(actions))
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - Failed: %s files", len(self._parse_errors))
        if actions:
            logger.info("[ACTION_DISCOVERY] [DEBUG]   - Action names: %s", list(actions.keys()))
        if self._parse_errors:
            logger.info("[ACTION_DISCOVERY] [DEBUG]   - Parse errors: %s", self._parse_errors)

        if self._parse_errors:
            logger.warning(
                "[ACTION_DISCOVERY] Loaded %s actions with %s parse errors",
                len(actions), len(self._parse_errors)
            )
        else:
            logger.info("[ACTION_DISCOVERY] Successfully loaded %s actions", len(actions))

        return actions

    def _parse_action_file(self, yaml_file: Path) -> Optional[ActionDefinition]:
        """
        Parse a single action YAML file

        Args:
            yaml_file: Path to YAML file

        Returns:
            ActionDefinition or None if parsing fails

        Raises:
            Exception: If YAML parsing or validation fails
        """
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning("[ACTION_DISCOVERY] Empty YAML file: %s", yaml_file.name)
            return None

        # Extract metadata
        metadata_dict = data.get("metadata", {})
        action_name = metadata_dict.get("action_name", yaml_file.stem)

        # Auto-assign labels based on action category
        labels = metadata_dict.get("labels", [])
        if not labels:
            labels = self._infer_labels(action_name, data)

        metadata = ActionMetadata(
            action_name=action_name,
            action_type=metadata_dict.get("action_type", "JSON"),
            version=metadata_dict.get("version", "1.0.0"),
            date=metadata_dict.get("date"),
            status=metadata_dict.get("status", "active"),
            labels=labels,
            related_docs=metadata_dict.get("related_docs", []),
        )

        # Parse parameters
        parameters = []

        # Try to extract from optional_fields or required_fields sections
        for field in data.get("optional_fields", []):
            if isinstance(field, dict):
                parameters.append(
                    ActionParameter(
                        name=field.get("name", ""),
                        type=field.get("type", "string"),
                        required=False,
                        default=field.get("default"),
                        description=field.get("description"),
                    )
                )

        for field in data.get("required_fields", []):
            if isinstance(field, dict):
                parameters.append(
                    ActionParameter(
                        name=field.get("name", ""),
                        type=field.get("type", "string"),
                        required=True,
                        description=field.get("description"),
                    )
                )

        # Extract examples
        examples = data.get("examples", [])
        if not isinstance(examples, list):
            examples = []

        # Create action definition
        action_def = ActionDefinition(
            name=action_name,
            metadata=metadata,
            description=data.get("description", ""),
            syntax=data.get("syntax"),
            parameters=parameters,
            examples=examples,
            best_practices=data.get("best_practices", []),
            tips=data.get("tips", []),
        )

        return action_def

    def _infer_labels(self, action_name: str, data: Dict) -> List[str]:
        """
        Infer labels for an action based on its name and content

        Args:
            action_name: Name of the action
            data: Parsed YAML data

        Returns:
            List of inferred labels
        """
        labels = []

        # Label by action type
        description = data.get("description", "").lower()

        if any(term in action_name for term in ["grep", "find", "search"]):
            labels.append("search")
        elif any(
            term in action_name
            for term in ["file", "read", "create", "update", "propose"]
        ):
            labels.append("file-operations")
        elif any(term in action_name for term in ["cell", "notebook"]):
            labels.append("notebook")
        elif any(
            term in action_name for term in ["navigate", "open", "copy", "clipboard"]
        ):
            labels.append("utility")

        # Add runtime label for actions that execute repository operations
        if any(
            term in description
            for term in ["search", "repository", "code", "grep", "find"]
        ):
            labels.append("runtime")

        # Add ui label for interface actions
        if any(
            term in description for term in ["navigate", "interface", "ui", "route"]
        ):
            labels.append("ui")

        # Add proposal label for actions that propose changes
        if "propose" in action_name or "proposal" in description:
            labels.append("proposal")

        # Default label
        if not labels:
            labels.append("general")

        return labels

    def _build_labels_index(self) -> Dict[str, List[str]]:
        """
        Build an index of labels to action names

        Returns:
            Dictionary mapping labels to list of action names
        """
        # DEBUG LOG: Check cache
        if self._labels_cache is not None:
            logger.info("[ACTION_DISCOVERY] [DEBUG] Using cached labels index: %s labels", len(self._labels_cache))
            return self._labels_cache

        logger.info("[ACTION_DISCOVERY] [DEBUG] Building labels index from actions")

        actions = self._load_actions()

        # DEBUG LOG: Actions loaded
        logger.info("[ACTION_DISCOVERY] [DEBUG] Building index from %s actions", len(actions))

        labels_index = {}

        for action_name, action_def in actions.items():
            logger.info(
                "[ACTION_DISCOVERY] [DEBUG] Processing action '%s' with labels: %s",
                action_name, action_def.metadata.labels
            )
            for label in action_def.metadata.labels:
                if label not in labels_index:
                    labels_index[label] = []
                labels_index[label].append(action_name)

        # DEBUG LOG: Final index
        logger.info("[ACTION_DISCOVERY] [DEBUG] Labels index built:")
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - Total labels: %s", len(labels_index))
        logger.info("[ACTION_DISCOVERY] [DEBUG]   - Labels: %s", list(labels_index.keys()))
        for label, action_names in labels_index.items():
            logger.info("[ACTION_DISCOVERY] [DEBUG]   - %s: %s", label, action_names)

        self._labels_cache = labels_index
        return labels_index

    def discover_all(self) -> Dict[str, List[str]]:
        """
        Discover all available labels and their associated actions

        Returns:
            Dictionary mapping labels to action names
            Example: {
                "search": ["grep", "find"],
                "file-operations": ["read_file", "propose_file_update"],
                ...
            }
        """
        return self._build_labels_index()

    def get_parse_errors(self) -> List[Dict[str, str]]:
        """
        Get list of files that failed to parse

        Returns:
            List of dictionaries with 'file' and 'error' keys
        """
        # Ensure actions are loaded first
        self._load_actions()
        return self._parse_errors

    def discover_by_label(self, label: str) -> List[Dict[str, Any]]:
        """
        Discover actions by label with their parameters

        Args:
            label: Label to filter by

        Returns:
            List of action definitions with parameters
            Example: [
                {
                    "name": "grep",
                    "description": "Search for patterns...",
                    "parameters": [
                        {"name": "pattern", "type": "string", "required": true},
                        ...
                    ]
                }
            ]
        """
        actions = self._load_actions()
        labels_index = self._build_labels_index()

        action_names = labels_index.get(label, [])

        result = []
        for action_name in action_names:
            action_def = actions.get(action_name)
            if action_def:
                result.append(
                    {
                        "name": action_def.name,
                        "description": action_def.description,
                        "parameters": [p.model_dump() for p in action_def.parameters],
                        "labels": action_def.metadata.labels,
                    }
                )

        return result

    def discover_action(self, label: str, action: str) -> Optional[Dict[str, Any]]:
        """
        Discover detailed information about a specific action

        Args:
            label: Label the action belongs to
            action: Action name

        Returns:
            Complete action definition with all metadata
            Example: {
                "name": "grep",
                "description": "...",
                "metadata": {...},
                "parameters": [...],
                "examples": [...],
                "best_practices": [...],
                "syntax": "..."
            }
        """
        actions = self._load_actions()
        action_def = actions.get(action)

        if not action_def:
            return None

        # Verify the action has the specified label
        if label not in action_def.metadata.labels:
            return None

        return {
            "name": action_def.name,
            "description": action_def.description,
            "metadata": action_def.metadata.model_dump(),
            "parameters": [p.model_dump() for p in action_def.parameters],
            "examples": action_def.examples,
            "best_practices": action_def.best_practices,
            "tips": action_def.tips,
            "syntax": action_def.syntax,
        }

    def refresh_cache(self):
        """Force refresh of the actions cache"""
        self._actions_cache = None
        self._labels_cache = None
        self._parse_errors = []
        logger.info("[ACTION_DISCOVERY] Cache refreshed")


# Global instance
_discovery_service: Optional[ActionDiscoveryService] = None


def get_discovery_service() -> ActionDiscoveryService:
    """
    Get or create the global action discovery service instance

    Returns:
        ActionDiscoveryService instance
    """
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = ActionDiscoveryService()
    return _discovery_service
