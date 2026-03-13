"""
Personal Access Token (PAT) API Router.

Implements endpoints for creating, listing, revoking, and regenerating PATs.

Security Model:
- Tokens are Ed25519-signed JWTs (asymmetric cryptography).
- The JWT is returned ONCE on creation and never stored in the database.
- The database stores only metadata: jwt_jti, token_prefix, scopes, expires_at.
- Revocation is immediate: sets is_active=False and revoked_at=now.
- Token validation uses the public key stored in artifacts/canonical/public_keys/.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user_required
from ..database import db
from ..models import (
    CreatePATRequest,
    CreatePATResponse,
    PATSummary,
    PersonalAccessToken,
    User,
)

logger = logging.getLogger(__name__)

tokens_router = APIRouter(prefix="/tokens", tags=["Access Tokens"])

# PAT token prefix used in the raw token string
_TOKEN_PREFIX = "sv_pat_"


def _generate_pat_jwt(
    user_id: str,
    user_nickname: Optional[str],
    scopes: List[str],
    expires_in_days: int,
) -> tuple[str, str, datetime]:
    """
    Generate an Ed25519-signed JWT for a PAT.

    Returns (raw_jwt, jti, expires_at).

    Signing key is loaded from the CENTRALHUB_PRIVATE_KEY environment variable
    (PEM-encoded Ed25519 private key). Falls back to a runtime-generated key when
    the environment variable is not set (development/test usage only — tokens
    issued without a configured key cannot be validated by other services).
    """
    try:
        import jwt as pyjwt
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        jti = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(days=expires_in_days)

        # Key ID for public key rotation — current year-month
        kid = now.strftime("%Y-%m")

        private_key_pem = os.environ.get("CENTRALHUB_PRIVATE_KEY", "")
        if not private_key_pem:
            raise RuntimeError(
                "CENTRALHUB_PRIVATE_KEY environment variable is not set. "
                "A PEM-encoded Ed25519 private key is required to issue PAT tokens. "
                "Generate a keypair and set CENTRALHUB_PRIVATE_KEY in your environment. "
                "See artifacts/canonical/public_keys/README.md for instructions."
            )

        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        private_key = load_pem_private_key(
            private_key_pem.encode(), password=None
        )

        payload = {
            "sub": user_id,
            "unick": user_nickname or "",
            "scopes": scopes,
            "jti": jti,
            "iat": now,
            "exp": expires_at,
            "nbf": now,
        }
        headers = {
            "alg": "EdDSA",
            "kid": kid,
            "typ": "JWT",
        }

        raw_jwt: str = pyjwt.encode(
            payload,
            private_key,
            algorithm="EdDSA",
            headers=headers,
        )

        return raw_jwt, jti, expires_at

    except ImportError as exc:
        raise RuntimeError(
            "PyJWT with cryptography support is required for PAT generation"
        ) from exc


@tokens_router.post("", response_model=CreatePATResponse, status_code=status.HTTP_201_CREATED)
async def create_token(
    request: CreatePATRequest,
    current_user: User = Depends(get_current_user_required),
):
    """
    Create a new Personal Access Token.

    The full token is returned **once only**. Copy it immediately — it cannot be
    retrieved after this response.

    Inputs:
    - name: human-readable token label (e.g. "runner-prod")
    - scopes: list of scopes to grant
    - expires_in_days: validity period (1–365 days)
    - environment: 'production', 'staging', or 'development'
    """
    try:
        raw_jwt, jti, expires_at = _generate_pat_jwt(
            user_id=current_user.id,
            user_nickname=getattr(current_user, "user_nickname", None),
            scopes=request.scopes,
            expires_in_days=request.expires_in_days,
        )
    except RuntimeError as exc:
        logger.error("PAT generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token generation failed",
        ) from exc

    token_prefix = raw_jwt[:8]
    full_token = f"{_TOKEN_PREFIX}{raw_jwt}"

    pat = PersonalAccessToken(
        user_id=current_user.id,
        name=request.name,
        token_prefix=token_prefix,
        jwt_jti=jti,
        scopes=request.scopes,
        expires_at=expires_at,
        environment=request.environment,
    )

    try:
        await db.insert(
            "service_tokens",
            pat,
            current_user=current_user,
        )
    except Exception as exc:
        logger.error("Failed to persist PAT record: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save token record",
        ) from exc

    logger.info("PAT '%s' created for user %s (jti=%s)", request.name, current_user.id, jti)

    return CreatePATResponse(
        token=full_token,
        token_prefix=token_prefix,
        pat_id=pat.id,
        expires_at=expires_at,
    )


@tokens_router.get("", response_model=List[PATSummary])
async def list_tokens(
    current_user: User = Depends(get_current_user_required),
):
    """
    List all active Personal Access Tokens for the authenticated user.

    Returns metadata only — no plaintext tokens.
    """
    try:
        # NOTE on RBAC filtering strategy:
        # db.find_many(..., current_user=current_user) validates that the user
        # has PERMISSION to access the collection, but does NOT filter records
        # by user_id. The manual filter below is intentional and necessary to
        # return only the tokens owned by the requesting user.
        all_pats = await db.find_many(
            "service_tokens",
            current_user=current_user,
            model_class=PersonalAccessToken,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error listing PATs: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing tokens",
        ) from exc

    user_pats = [p for p in all_pats if p.user_id == current_user.id]

    return [
        PATSummary(
            id=p.id,
            name=p.name,
            token_prefix=p.token_prefix,
            scopes=p.scopes,
            created_at=p.created_at,
            expires_at=p.expires_at,
            last_used_at=p.last_used_at,
            is_active=p.is_active,
            revoked_at=p.revoked_at,
            environment=p.environment,
        )
        for p in user_pats
    ]


@tokens_router.get("/{token_id}", response_model=PATSummary)
async def get_token(
    token_id: str,
    current_user: User = Depends(get_current_user_required),
):
    """
    Retrieve metadata for a specific Personal Access Token.

    No plaintext token is ever returned.
    """
    try:
        pat = await db.find_one(
            "service_tokens",
            token_id,
            current_user=current_user,
            model_class=PersonalAccessToken,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error retrieving PAT %s: %s", token_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving token",
        ) from exc

    if not pat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Token {token_id} not found",
        )

    if pat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own tokens",
        )

    return PATSummary(
        id=pat.id,
        name=pat.name,
        token_prefix=pat.token_prefix,
        scopes=pat.scopes,
        created_at=pat.created_at,
        expires_at=pat.expires_at,
        last_used_at=pat.last_used_at,
        is_active=pat.is_active,
        revoked_at=pat.revoked_at,
        environment=pat.environment,
    )


@tokens_router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: str,
    current_user: User = Depends(get_current_user_required),
):
    """
    Revoke a Personal Access Token immediately.

    Sets is_active=False and records revoked_at. Revoked tokens return 401 on any
    subsequent use.
    """
    try:
        pat = await db.find_one(
            "service_tokens",
            token_id,
            current_user=current_user,
            model_class=PersonalAccessToken,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error looking up PAT %s for revocation: %s", token_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error revoking token",
        ) from exc

    if not pat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Token {token_id} not found",
        )

    if pat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only revoke your own tokens",
        )

    if not pat.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Token is already revoked",
        )

    try:
        await db.update(
            "service_tokens",
            token_id,
            {"is_active": False, "revoked_at": datetime.utcnow()},
            current_user=current_user,
        )
    except Exception as exc:
        logger.error("Error persisting revocation for PAT %s: %s", token_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error revoking token",
        ) from exc

    logger.info("PAT %s revoked by user %s", token_id, current_user.id)


@tokens_router.post("/{token_id}/regenerate", response_model=CreatePATResponse)
async def regenerate_token(
    token_id: str,
    expires_in_days: int = 90,
    current_user: User = Depends(get_current_user_required),
):
    """
    Regenerate a Personal Access Token.

    Revokes the existing token and issues a new JWT with the same name, scopes,
    and environment. The new token is shown **once only** — copy it immediately.

    Query parameter:
    - expires_in_days: validity of the new token (default: 90, range: 1–365)
    """
    try:
        pat = await db.find_one(
            "service_tokens",
            token_id,
            current_user=current_user,
            model_class=PersonalAccessToken,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error retrieving PAT %s for regeneration: %s", token_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error regenerating token",
        ) from exc

    if not pat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Token {token_id} not found",
        )

    if pat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only regenerate your own tokens",
        )

    if not 1 <= expires_in_days <= 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="expires_in_days must be between 1 and 365",
        )

    # Revoke the old token
    try:
        await db.update(
            "service_tokens",
            token_id,
            {"is_active": False, "revoked_at": datetime.utcnow()},
            current_user=current_user,
        )
    except Exception as exc:
        logger.error("Error revoking old PAT %s during regeneration: %s", token_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error regenerating token",
        ) from exc

    try:
        raw_jwt, jti, expires_at = _generate_pat_jwt(
            user_id=current_user.id,
            user_nickname=getattr(current_user, "user_nickname", None),
            scopes=pat.scopes,
            expires_in_days=expires_in_days,
        )
    except RuntimeError as exc:
        logger.error("PAT re-generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token generation failed",
        ) from exc

    token_prefix = raw_jwt[:8]
    full_token = f"{_TOKEN_PREFIX}{raw_jwt}"

    new_pat = PersonalAccessToken(
        user_id=current_user.id,
        name=pat.name,
        token_prefix=token_prefix,
        jwt_jti=jti,
        scopes=pat.scopes,
        expires_at=expires_at,
        environment=pat.environment,
    )

    try:
        await db.insert(
            "service_tokens",
            new_pat,
            current_user=current_user,
        )
    except Exception as exc:
        logger.error("Failed to persist regenerated PAT record: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save regenerated token record",
        ) from exc

    logger.info(
        "PAT '%s' regenerated for user %s (old_id=%s, new_id=%s)",
        pat.name,
        current_user.id,
        token_id,
        new_pat.id,
    )

    return CreatePATResponse(
        token=full_token,
        token_prefix=token_prefix,
        pat_id=new_pat.id,
        expires_at=expires_at,
    )
