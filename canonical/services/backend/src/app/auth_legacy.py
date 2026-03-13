"""
Authentication and OAuth2 handling for ScareVerse.

Implements:
- Google OAuth2 authentication
- JWT token generation and validation
- Session management
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import ADMIN_EMAIL, ENCRYPTION_KEY, GOOGLE_CLIENT_ID
from .database import db
from .models import Session, User

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = ENCRYPTION_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 1 week
SESSION_EXPIRE_DAYS = 7  # Session expiration in days

# Security scheme
security = HTTPBearer(auto_error=False)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# System user for internal operations (pre-auth, system tasks)
# This user bypasses RBAC for pre-authentication queries (e.g., finding user by email during login)
SYSTEM_USER = User(
    id="system",
    email="system@scareverse.internal",
    name="System",
    roles=["admin"],
    permissions=["*"],  # Full access
)


def create_access_token(
    data: Union[dict, User], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token with roles, permissions, and jti.

    Args:
        data: Either a User object or dict for backward compatibility
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token

    JWT Payload includes:
        - sub: User ID
        - jti: Unique JWT ID (for revocation)
        - roles: User roles array
        - permissions: User permissions array
        - session_id: Session identifier (if provided)
        - exp: Expiration timestamp
        - iat: Issued at timestamp
        - type: Token type ("access")
    """
    # Handle both User object and dict for backward compatibility
    if isinstance(data, User):
        # New API: User object with roles and permissions
        user = data
        jti = str(uuid.uuid4())

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

        payload = {
            "sub": user.id,
            "jti": jti,
            "roles": user.roles if user.roles else [],
            "permissions": user.permissions if user.permissions else [],
            "session_id": getattr(user, "session_id", None),
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
        }

        logger.info("JWT created | user=%s | jti=%s | roles=%s | perms=%s", user.id, jti, user.roles, user.permissions)
    else:
        # Backward compatibility: dict-based API
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

        to_encode.update({"exp": expire})

        # Add jti, iat and type for consistency
        if "jti" not in to_encode:
            to_encode["jti"] = str(uuid.uuid4())
        if "iat" not in to_encode:
            to_encode["iat"] = datetime.utcnow()
        if "type" not in to_encode:
            to_encode["type"] = "access"

        payload = to_encode

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token to verify

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning("JWT verification failed: %s", e)
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[User]:
    """
    Get current authenticated user from JWT token (optional).

    Returns None if no valid token is provided.
    Used for endpoints that work in both authenticated and open mode.

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        User object if authenticated, None otherwise
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = verify_token(token)

    if not payload:
        logger.debug("[AUTH] Could not validate credentials from token")
        return None

    user_id: str = payload.get("sub")
    if not user_id:
        logger.warning("[AUTH] Token payload missing 'sub' field")
        return None

    # Construct User directly from JWT payload (no database query)
    user = User(
        id=user_id,
        email=payload.get("email", ""),
        name=payload.get("name", ""),
        roles=payload.get("roles", []),
        permissions=payload.get("permissions", []),
    )

    logger.debug("[AUTH] User authenticated from JWT: %s", user.id)
    return user


async def get_current_user_required(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Get current authenticated user - required.

    Constructs User object directly from JWT payload without database queries.
    JWT is the source of truth for user identity and permissions.

    Raises HTTPException if user is not authenticated.

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        User object with id, email, name, roles, permissions from JWT

    Raises:
        HTTPException: If token is missing, invalid, or missing required fields
    """
    if not credentials:
        logger.warning("[AUTH] 401: Not authenticated - missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = verify_token(token)

    if not payload:
        logger.warning(
            "[AUTH] 401: Could not validate credentials - token signature or expiration invalid"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("sub")
    if not user_id:
        logger.warning("[AUTH] 401: Token payload missing 'sub' (user_id) field")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Construct User directly from JWT payload (no database query needed)
    # JWT is the source of truth for user identity and permissions
    user = User(
        id=user_id,
        email=payload.get("email", ""),
        name=payload.get("name", ""),
        roles=payload.get("roles", []),
        permissions=payload.get("permissions", []),
    )

    logger.info("[AUTH] User authenticated from JWT: %s (roles=%s)", user.id, user.roles)
    return user


async def get_current_session(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Session]:
    """
    Get current session from JWT token.

    Session ID is extracted from JWT payload. If CentralHub issued the token,
    it already validated the session exists and is active.

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        Session object if valid, None otherwise
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = verify_token(token)

    if not payload:
        return None

    session_id: str = payload.get("session_id")
    if not session_id:
        logger.debug("[AUTH] No session_id in token")
        return None

    # Construct Session directly from JWT (CentralHub already validated it)
    # session_id is present only if CentralHub validated the session exists and is active
    session = Session(
        id=session_id,
        user_id=payload.get("sub", ""),
        active=True,  # If we have a valid token, session must be active
    )

    logger.debug("[AUTH] Session from JWT: %s", session.id)
    return session


def create_oauth_client(client_id: str, client_secret: str) -> OAuth:
    """
    Create OAuth client for Google authentication.

    Args:
        client_id: Google Client ID
        client_secret: Google Client Secret

    Returns:
        Configured OAuth client
    """
    oauth = OAuth()

    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    return oauth


def verify_google_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Google OAuth2 ID token.

    Args:
        token: Google ID token (JWT) to verify

    Returns:
        Decoded token payload with user info, or None if invalid
    """
    if not GOOGLE_CLIENT_ID:
        logger.error("GOOGLE_CLIENT_ID not configured")
        return None

    try:
        # Verify the token using Google's library
        idinfo = id_token.verify_oauth2_token(
            token, google_requests.Request(), GOOGLE_CLIENT_ID
        )

        # Verify the issuer
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            logger.warning("Invalid token issuer: %s", idinfo['iss'])
            return None

        logger.info("Google token verified for user: %s", idinfo.get('email'))
        logger.info(
            "[AUTH] JWT token generated: sub=%s, session_id=%s, exp=%s",
            idinfo.get('sub'), idinfo.get('session_id'), idinfo.get('exp')
        )
        return idinfo

    except ValueError as e:
        # Invalid token
        logger.warning("Google token verification failed: %s", e)
        return None
    except Exception as e:
        logger.error("Error verifying Google token: %s", e)
        return None


async def get_current_user_google(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Get current authenticated user from Google OAuth2 token.

    This validates the Google JWT token sent by the frontend and returns
    the corresponding user from the database. If the user doesn't exist,
    it creates a new user automatically.

    Args:
        credentials: HTTP Bearer token credentials with Google JWT

    Returns:
        User object

    Raises:
        HTTPException: If token is invalid or user cannot be authenticated
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured - GOOGLE_CLIENT_ID missing",
        )

    token = credentials.credentials
    idinfo = verify_google_token(token)

    if not idinfo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    google_id = idinfo.get("sub")
    email = idinfo.get("email")

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload - missing user info",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get name from token, or derive from email
    name = idinfo.get("name")
    if not name:
        name = email.split("@")[0]

    # Try to find existing user by Google ID
    try:
        users = await db.find(
            "users",
            {"googleId": google_id},
            current_user=SYSTEM_USER,
        )
        user = users[0] if users else None
        if user and isinstance(user, dict):
            user = User(**user)
    except Exception as e:
        logger.error("[AUTH] Error fetching user by googleId %s: %s: %s", google_id, type(e).__name__, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during authentication",
        )

    if not user:
        # Try to find by email
        try:
            users = await db.find(
                "users",
                {"email": email},
                current_user=SYSTEM_USER,
            )
            user = users[0] if users else None
            if user and isinstance(user, dict):
                user = User(**user)
        except Exception as e:
            logger.error("[AUTH] Error fetching user by email %s: %s: %s", email, type(e).__name__, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error during authentication",
            )

        if user:
            # Update existing user with Google ID
            await db.update(
                "users", user.id, {"googleId": google_id}, current_user=SYSTEM_USER
            )
            user.googleId = google_id
            logger.info("Updated existing user %s with Google ID", user.id)
        else:
            # Create new user automatically
            # NOTE: There's a potential race condition where concurrent requests
            # could create duplicate users. This should be handled with database
            # constraints (unique email/googleId) or transactions in production.
            initial_roles = get_initial_user_roles(email)
            user = User(name=name, email=email, googleId=google_id, roles=initial_roles)
            user_dict = user.model_dump()
            await db.insert("users", user_dict, current_user=SYSTEM_USER)
            logger.info("Created new user from Google auth: %s (%s) with roles: %s", user.id, email, initial_roles)

    return user


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_initial_user_roles(email: str) -> list[str]:
    """
    Determine initial roles for a new user based on email.

    Checks if the email matches ADMIN_EMAIL from configuration.
    Admin users receive ["admin"] role, others receive ["user"] role.

    Args:
        email: User's email address

    Returns:
        List of role names to assign to the user
    """
    # Handle case where ADMIN_EMAIL is not configured
    if not ADMIN_EMAIL:
        logger.warning("ADMIN_EMAIL not configured, defaulting to user role")
        return ["user"]

    # Handle case where email is empty or None
    if not email:
        return ["user"]

    # Case-insensitive email comparison to handle variations
    if email.lower() == ADMIN_EMAIL.lower():
        logger.info("Assigning admin role to user with email: %s", email)
        return ["admin"]
    else:
        return ["user"]


async def get_user_from_token_query(
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """
    Get authenticated user from either query parameter token or Authorization header.

    This is specifically designed for SSE endpoints where EventSource doesn't support
    custom headers. The token can be passed via query parameter as a fallback.

    Args:
        token: Optional JWT token from query parameter
        credentials: Optional HTTP Bearer token credentials from header

    Returns:
        User object

    Raises:
        HTTPException: If user is not authenticated
    """
    logger.info("[AUTH] Attempting SSE authentication (query or header)")

    # Try to get token from header first
    auth_token = None
    if credentials:
        auth_token = credentials.credentials
        logger.debug("[AUTH] Token found in Authorization header")
    elif token:
        auth_token = token
        logger.debug("[AUTH] Token found in query parameter")

    if not auth_token:
        logger.warning("[AUTH] 401: Not authenticated - no token in header or query")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - token required in Authorization header or query parameter",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token
    payload = verify_token(auth_token)

    if not payload:
        logger.warning("[AUTH] 401: Could not validate credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("[AUTH] Token payload: %s", payload)

    # Extract user ID
    user_id: str = payload.get("sub")
    if not user_id:
        logger.warning("[AUTH] 401: Token payload missing 'sub' field")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("[AUTH] Fetching user with ID: %s", user_id)

    # Get user from database
    try:
        user = await db.find_one(
            "users", user_id, current_user=SYSTEM_USER, model_class=User
        )
    except RuntimeError as e:
        logger.error("[AUTH] 500: Database error while fetching user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while authenticating user",
        )
    except Exception as e:
        logger.error("[AUTH] 500: Unexpected error while fetching user %s: %s: %s", user_id, type(e).__name__, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while authenticating user",
        )

    if not user:
        logger.warning("[AUTH] 401: User not found for user_id: %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("[AUTH] User authenticated successfully: %s", user.email)

    return user
