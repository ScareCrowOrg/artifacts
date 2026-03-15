"""
artifacts/shared – Python utilities shared across all ScareVerse services.

Provides:
  - ``secret_client``: TOTP-authenticated secret requests from the Launcher.
  - ``config_manager``: Unified configuration resolution (Redis + secrets + env).
  - ``crypto``: Cryptographic utilities (TOTP, AES-GCM).
"""

from .secret_client import SecretClient
from .config_manager import get_config

__all__ = [
    "SecretClient",
    "get_config",
]
