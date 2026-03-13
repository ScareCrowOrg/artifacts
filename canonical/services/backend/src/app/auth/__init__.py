"""
Authentication module for ScareVerse Backend.

Provides JWT context management for forwarding authentication to CentralHub.
Also re-exports legacy authentication functions for backward compatibility
during the authentication migration (centralization to CentralHub).
"""

# Re-export legacy authentication functions from auth_legacy.py for backward compatibility
# These are still used by existing routers and should continue working during migration
from ..auth_legacy import (
    SYSTEM_USER,
    get_current_user,
    get_current_user_google,
    get_current_user_required,
    get_initial_user_roles,
    get_user_from_token_query,
)
from .context import (
    get_current_token,
    get_user_id_from_token,
    set_current_token,
    verify_token,
)

__all__ = [
    # New context-based functions (CentralHub integration)
    "set_current_token",
    "get_current_token",
    "get_user_id_from_token",
    # Legacy functions for backward compatibility
    "get_current_user",
    "get_current_user_required",
    "get_current_user_google",
    "get_initial_user_roles",
    "get_user_from_token_query",
    "SYSTEM_USER",
    "verify_token",
]
