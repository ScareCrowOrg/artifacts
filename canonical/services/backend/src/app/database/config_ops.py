"""
Configuration operations for JSONDatabase.

Handles get/set operations for configuration values stored as JSON files.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ConfigOperations:
    """
    Configuration operations mixin for JSONDatabase.

    Provides methods for getting and setting configuration values.
    """

    def get_config(self, config_key: str) -> Optional[Dict[str, Any]]:
        """
        Get a configuration value.

        Args:
            config_key: Configuration key

        Returns:
            Configuration value as dict or None
        """
        config_path = self.base_path / "config" / f"{config_key}.json"

        if not config_path.exists():
            return None

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error reading config %s: %s", config_key, e)
            return None

    def set_config(self, config_key: str, config_value: Dict[str, Any]) -> bool:
        """
        Set a configuration value.

        Args:
            config_key: Configuration key
            config_value: Configuration value as dict

        Returns:
            True if successful, False otherwise
        """
        config_dir = self.base_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / f"{config_key}.json"

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_value, f, indent=2, ensure_ascii=False, default=str)
            logger.info("Config %s saved successfully", config_key)
            return True
        except Exception as e:
            logger.error("Error saving config %s: %s", config_key, e)
            return False
