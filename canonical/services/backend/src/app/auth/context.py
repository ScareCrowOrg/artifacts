"""
JWT Context Management for Backend-to-CentralHub Authentication.

This module provides ContextVar-based storage for JWT tokens captured from
incoming requests. The tokens are forwarded to CentralHub for validation,
ensuring proper authentication chain:

Flow:
1. Frontend sends request with JWT to Backend (Authorization: Bearer <token>)
2. Middleware captures JWT and stores in ContextVar
3. CentralHubClient retrieves JWT from ContextVar
4. CentralHubClient forwards JWT to CentralHub in Authorization header
5. CentralHub validates JWT and extracts authenticated user_id
6. CentralHub verifies user_id matches request body (if present)

Security:
- JWT is only stored for the duration of the request (ContextVar is request-scoped)
- No JWT validation in Backend (delegated to CentralHub for single source of truth)
- User_id extraction is optional and doesn't require validation (CentralHub validates)
"""

import logging
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger(__name__)

# ContextVar for storing JWT token per request
# This is automatically isolated per async task (request context)
_token_ctx_var: ContextVar[Optional[str]] = ContextVar("request_token", default=None)


def set_current_token(token: str) -> None:
    """
    Store JWT token in request context.

    Called by middleware when processing incoming requests with Authorization header.

    Args:
        token: JWT token from Authorization header (without "Bearer " prefix)

    Example:
        >>> set_current_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    """
    _token_ctx_var.set(token)
    logger.debug("JWT token stored in request context")


def get_current_token() -> Optional[str]:
    """
    Retrieve JWT token from request context.

    Returns:
        JWT token if available, None otherwise

    Example:
        >>> token = get_current_token()
        >>> if token:
        ...     headers = {"Authorization": f"Bearer {token}"}
    """
    return _token_ctx_var.get()


def get_user_id_from_token(token: Optional[str] = None) -> Optional[str]:
    """
    Extract user_id from JWT token WITHOUT validation.

    This is a convenience function for extracting user_id from the token payload
    without validating the signature. CentralHub will perform full validation.

    Args:
        token: JWT token to extract user_id from (optional, uses current token if None)

    Returns:
        user_id (sub claim) if present, None otherwise

    Security Note:
        This function does NOT validate the JWT signature or expiration.
        It's safe to use because:
        1. The token will be validated by CentralHub before use
        2. We only extract user_id for convenience (e.g., logging, cache keys)
        3. All security decisions are made by CentralHub after full validation

    Example:
        >>> user_id = get_user_id_from_token(token)
        >>> logger.info(f"Request from user: {user_id}")  # Safe for logging
    """
    if token is None:
        token = get_current_token()

    if not token:
        return None

    try:
        from jose import jwt

        # Decode WITHOUT verification (CentralHub will verify)
        # Note: When verification is disabled, the key parameter is ignored
        # We only extract user_id for convenience (logging, cache keys)
        # Security validation happens in CentralHub
        payload = jwt.decode(
            token, options={"verify_signature": False, "verify_exp": False}
        )
        return payload.get("sub")
    except Exception as e:
        logger.warning("Failed to extract user_id from token: %s", e)
        return None


def verify_token(token: Optional[str] = None) -> Optional[dict]:
    """
    Verify and decode JWT token with full validation.

    Used for WebSocket and other long-lived connections that need local validation
    without making a request to CentralHub.

    Args:
        token: JWT token to verify (optional, uses current token if None)

    Returns:
        Token payload (dict) if valid, None if invalid/expired

    Security:
        - Validates JWT signature using ENCRYPTION_KEY
        - Validates expiration time
        - Returns None for any validation failure

    Example:
        >>> payload = verify_token(token)
        >>> if payload:
        ...     user_id = payload.get("sub")
    """
    import os

    from jose import JWTError, jwt

    if token is None:
        token = get_current_token()

    if not token:
        return None

    try:
        secret_key = os.getenv("ENCRYPTION_KEY", "")
        if not secret_key:
            logger.error("ENCRYPTION_KEY not set, cannot verify token")
            return None

        # Decode WITH verification (validates signature and expiration)
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
            options={"verify_signature": True, "verify_exp": True},
        )
        return payload
    except JWTError as e:
        logger.warning("JWT verification failed: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error verifying token: %s", e)
        return None
