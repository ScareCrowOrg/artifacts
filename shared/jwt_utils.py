"""
Shared Ed25519 JWT utilities for CentralHub and ScareRunner.

Provides sign/verify helpers that use asymmetric Ed25519 cryptography so that
the private signing key never needs to leave CentralHub.

Public keys are loaded once at startup from
``artifacts/canonical/public_keys/*.pub`` (one file per key rotation period,
named ``YYYY-MM.pub``).  The ``kid`` JWT header claim selects the correct key.

Environment variables
---------------------
CENTRALHUB_PRIVATE_KEY
    PEM-encoded Ed25519 private key used for signing (CentralHub only).
    Literal ``\\n`` characters are automatically converted to real newlines so
    the value can be stored as a single-line environment variable.
PUBLIC_KEYS_DIR
    Optional override for the public-keys directory path.  Defaults to
    ``artifacts/canonical/public_keys`` relative to the project root.
"""

import logging
import os
from datetime import datetime, timezone
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
# JWT signing (CentralHub only)
# ---------------------------------------------------------------------------


def sign_jwt(
    payload: Dict[str, Any],
    private_key_pem: str,
    kid: Optional[str] = None,
) -> str:
    """
    Sign a JWT payload with an Ed25519 private key.

    Args:
        payload: JWT claims dict (must include ``exp``).
        private_key_pem: PEM-encoded Ed25519 private key.  Literal ``\\n``
            escape sequences are converted to real newlines automatically.
        kid: Key ID embedded in the JWT ``kid`` header claim.  Defaults to
            the current UTC year-month (``YYYY-MM``).

    Returns:
        Encoded JWT string.

    Raises:
        RuntimeError: If the private key is empty or cannot be loaded.
        ImportError: If PyJWT with cryptography support is not installed.
    """
    import jwt as pyjwt
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    if not private_key_pem:
        raise RuntimeError(
            "CENTRALHUB_PRIVATE_KEY is not set. "
            "A PEM-encoded Ed25519 private key is required to sign JWTs. "
            "See artifacts/canonical/public_keys/README.md for instructions."
        )

    if kid is None:
        kid = datetime.now(timezone.utc).strftime("%Y-%m")

    # Convert literal \n escape sequences (common in env-var storage) to real newlines
    private_key_pem = private_key_pem.replace("\\n", "\n")

    try:
        private_key = load_pem_private_key(private_key_pem.encode(), password=None)
    except Exception as exc:
        raise RuntimeError(f"Failed to load Ed25519 private key: {exc}") from exc

    headers = {"alg": "EdDSA", "kid": kid, "typ": "JWT"}

    return pyjwt.encode(payload, private_key, algorithm="EdDSA", headers=headers)


# ---------------------------------------------------------------------------
# JWT verification (ScareRunner and CentralHub middleware)
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

    try:
        header = pyjwt.get_unverified_header(token)
    except pyjwt.DecodeError as exc:
        logger.warning("JWT header decode error: %s", exc)
        return None

    kid = header.get("kid")
    if not kid:
        logger.warning("JWT is missing 'kid' in header")
        return None

    pub_key = public_keys.get(kid)
    if pub_key is None:
        logger.warning(
            "Unknown JWT kid '%s' (available: %s)", kid, sorted(public_keys.keys())
        )
        return None

    try:
        payload: Dict[str, Any] = pyjwt.decode(
            token, pub_key, algorithms=["EdDSA"]
        )
        return payload
    except pyjwt.ExpiredSignatureError as exc:
        logger.warning("JWT expired: %s", exc)
        return None
    except pyjwt.InvalidSignatureError as exc:
        logger.warning("JWT invalid signature: %s", exc)
        return None
    except pyjwt.DecodeError as exc:
        logger.warning("JWT decode error: %s", exc)
        return None
    except Exception as exc:
        logger.error("Unexpected JWT verification error: %s", exc)
        return None
