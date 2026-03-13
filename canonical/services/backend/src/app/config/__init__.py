"""
Configuration Package - ScareVerse Backend

This package contains modular configuration files and re-exports
all configuration from the main config module for backward compatibility.

Usage:
    # Database configuration (new centralized location)
    from app.config.database import MONGODB_CONFIG, REDIS_CONFIG

    # All configuration (backward compatible)
    from app.config import BASE_DIR, MONGODB_HOST, REDIS_HOST, etc.
    # or
    import app.config
    app.config.BASE_DIR
"""

# Import database configuration first
# Import all other configuration from parent config module
# We need to do this carefully to avoid circular imports
import sys
from pathlib import Path

from .database import *

# Get the config.py module (not the config package)
config_module_path = Path(__file__).parent.parent / "config.py"
if config_module_path.exists():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_app_config_module", config_module_path
    )
    if spec and spec.loader:
        config_module = importlib.util.module_from_spec(spec)
        sys.modules["app._config_module"] = config_module
        spec.loader.exec_module(config_module)

        # Re-export all configuration from config.py
        # This makes app.config work as before while also having config.database
        for name in dir(config_module):
            if not name.startswith("_"):
                globals()[name] = getattr(config_module, name)
