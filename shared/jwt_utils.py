"""
Shared Ed25519 JWT verification utilities.

Provides verify helpers that use asymmetric Ed25519 cryptography.
Public keys are loaded once at startup from
``artifacts/canonical/public_keys/*.pub`` (one file per key rotation period,
named ``YYYY-MM.pub``).  The ``kid`` JWT header claim selects the correct key.

Used by:
- CentralHub (verifying tokens in HTTP endpoints)
- Backend (verifying tokens for WebSocket connections)
- Any other service that needs to validate JWT tokens

Environment variables
---------------------
PUBLIC_KEYS_DIR
    Optional override for the public-keys directory path.  Defaults to
    ``artifacts/canonical/public_keys`` relative to the project root.

Note: JWT signing (sign_jwt) is handled by CentralHub's jwt_service module.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path discovery
# ---------------------------------------------------------------------------

# Project root = grandparent of this file (artifacts/shared/jwt_utils.py)
# artifacts/shared/ → artifacts/ → project-root
# Allow override via PROJECT_ROOT env var for editable installs or symlinks.
_PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT") or Path(__file__).parent.parent.parent)
_DEFAULT_PUBLIC_KEYS_DIR = _PROJECT_ROOT / "artifacts" / "canonical" / "public_keys"


def _get_public_keys_dir() -> Path:
    override = os.getenv("PUBLIC_KEYS_DIR")
    if override:
        return Path(override)
    return _DEFAULT_PUBLIC_KEYS_DIR


# ---------------------------------------------------------------------------
# Public key loading
# ---------------------------------------------------------------------------


def load_public_keys(pub_keys_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load all Ed25519 public keys from the public-keys directory.

    Returns a mapping of ``kid`` → loaded public-key object (ready for
    ``jwt.decode``).  Files that fail to parse are skipped with a warning.

    Args:
        pub_keys_dir: Override directory path.  Defaults to
            ``artifacts/canonical/public_keys``.
    """
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    if pub_keys_dir is None:
        pub_keys_dir = _get_public_keys_dir()

    keys: Dict[str, Any] = {}
    pub_keys_path = Path(pub_keys_dir)

    if not pub_keys_path.exists():
        logger.warning("Public keys directory not found: %s", pub_keys_path)
        return keys

    for pub_file in sorted(pub_keys_path.glob("*.pub")):
        kid = pub_file.stem
        try:
            key_pem = pub_file.read_text().strip()
            pub_key = load_pem_public_key(key_pem.encode())
            keys[kid] = pub_key
            logger.debug("Loaded public key: %s", kid)
        except Exception as exc:
            logger.warning("Failed to load public key '%s': %s", kid, exc)

    if keys:
        logger.info("Loaded %d public key(s): %s", len(keys), sorted(keys.keys()))
    else:
        logger.warning("No public keys loaded from: %s", pub_keys_path)

    return keys


# ---------------------------------------------------------------------------
# JWT verification (all services)
# ---------------------------------------------------------------------------


def verify_jwt(
    token: str,
    public_keys: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Verify a JWT using Ed25519 public keys.

    Extracts the ``kid`` from the unverified JWT header, looks up the
    corresponding public key, then verifies the signature and expiration.

    Args:
        token: JWT string to verify.
        public_keys: Mapping of ``kid`` → public-key object (from
            :func:`load_public_keys`).

    Returns:
        Decoded JWT payload dict on success, ``None`` on any failure
        (expired, invalid signature, unknown kid, malformed token).
    """
    import jwt as pyjwt

    # Anonymize token for logging (show only first 50 chars + "...")
    token_preview = token[:50] + "..." if len(token) > 50 else token

    try:
        header = pyjwt.get_unverified_header(token)
        logger.debug(f"[verify_jwt] ✓ Decoded JWT header: {header}")
    except pyjwt.DecodeError as exc:
        logger.warning(f"[verify_jwt] ✗ JWT header decode error: {exc} (token: {token_preview})")
        return None

    kid = header.get("kid")
    alg = header.get("alg")
    typ = header.get("typ")

    logger.info(f"[verify_jwt] Token header: kid='{kid}', alg='{alg}', typ='{typ}'")

    if not kid:
        logger.warning("[verify_jwt] ✗ JWT is missing 'kid' in header")
        return None

    logger.info(f"[verify_jwt] Looking for kid='{kid}' (available keys: {sorted(public_keys.keys())})")

    pub_key = public_keys.get(kid)
    if pub_key is None:
        logger.error(
            f"[verify_jwt] ✗ Unknown JWT kid='{kid}' (available: {sorted(public_keys.keys())})"
        )
        return None

    logger.debug(f"[verify_jwt] ✓ Found public key for kid='{kid}'")

    try:
        payload: Dict[str, Any] = pyjwt.decode(
            token, pub_key, algorithms=["EdDSA"]
        )
        exp = payload.get("exp")
        iat = payload.get("iat")
        sub = payload.get("sub")
        logger.info(f"[verify_jwt] ✓ JWT signature valid: sub='{sub}', iat={iat}, exp={exp}")
        return payload
    except pyjwt.ExpiredSignatureError as exc:
        exp = None
        try:
            unverified_payload = pyjwt.decode(token, options={"verify_signature": False})
            exp = unverified_payload.get("exp")
        except:
            pass
        logger.warning(f"[verify_jwt] ✗ JWT expired (exp={exp}): {exc}")
        return None
    except pyjwt.InvalidSignatureError as exc:
        logger.error(f"[verify_jwt] ✗ JWT invalid signature (kid='{kid}'): {exc}")
        return None
    except pyjwt.DecodeError as exc:
        logger.warning(f"[verify_jwt] ✗ JWT decode error (kid='{kid}'): {exc}")
        return None
    except Exception as exc:
        logger.error(f"[verify_jwt] ✗ Unexpected JWT verification error (kid='{kid}'): {exc}")
        return None
