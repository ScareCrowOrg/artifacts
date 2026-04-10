"""
Secret Client – Request and decrypt secrets from the Launcher via Redis.

Phase 2: Services request secrets using TOTP validation.
Secrets are ephemeral: encrypted in Redis, decrypted in service memory only,
and cleaned up immediately after consumption.

Environment variables required:
    TOTP_SEED      – 64-char hex seed injected by the Launcher.
    REDIS_L1_HOST  – Redis L1 hostname (default: localhost).
    REDIS_L1_PORT  – Redis L1 port     (default: 6380).
    SERVICE_NAME   – Logical service identifier (default: backend).

Usage example::

    client = SecretClient(os.getenv("TOTP_SEED"))
    redis_password = client.request_secret("redis-password")
    r = redis.Redis(password=redis_password)
"""

import base64
import hashlib
import json
import logging
import os
import time
from typing import Optional

import redis as redis_lib

from .crypto.totp_validator import TOTPValidator


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level configuration (overridable via environment variables)
# ---------------------------------------------------------------------------

REDIS_HOST: str = os.getenv("REDIS_L1_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_L1_PORT", "6380"))
SERVICE_NAME: str = os.getenv("SERVICE_NAME", "backend")


# ---------------------------------------------------------------------------
# SecretClient
# ---------------------------------------------------------------------------


class SecretClient:
    """Request AES-256-GCM–encrypted secrets from the Launcher with TOTP validation."""

    def __init__(self, seed: str) -> None:
        """
        Initialise the client with the service's TOTP seed.

        Args:
            seed: 64-char hex string received via ``TOTP_SEED`` env var.
        """
        logger.debug(f"[SecretClient] Initializing with seed (length: {len(seed)} chars)")
        self._totp = TOTPValidator(seed)
        self._redis = redis_lib.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=False,
        )
        logger.info(f"[SecretClient] Connected to Redis L1 at {REDIS_HOST}:{REDIS_PORT}")

    def request_secret(self, secret_key: str, timeout: int = 5) -> Optional[str]:
        """
        Request a secret from the Launcher.

        Publishes a TOTP-authenticated request to Redis and polls for the
        encrypted response.  On success the secret is decrypted, the Redis
        key is deleted (best-effort), and the plaintext is returned.

        Args:
            secret_key: Logical name of the secret (e.g. ``"redis-password"``).
            timeout:    Maximum seconds to wait for the Launcher's response.

        Returns:
            Decrypted plaintext secret string, or ``None`` if the request
            timed out or the Launcher rejected it.
        """
        logger.info(f"[SecretClient] Requesting secret: {secret_key} (timeout: {timeout}s)")
        # Timestamp in milliseconds (matches the Launcher's TypeScript side).
        timestamp_ms = int(time.time() * 1000)
        totp_code = self._totp.generate_code(timestamp_ms // 1000)
        logger.debug(f"[SecretClient] Generated TOTP code for {secret_key}")

        request_payload = json.dumps(
            {
                "service": SERVICE_NAME,
                "secret_key": secret_key,
                "timestamp": timestamp_ms,
                "totp_code": totp_code,
            }
        )
        request_channel = f"request:secret:{SERVICE_NAME}:{secret_key}"
        self._redis.set(request_channel, request_payload)

        # Poll for the encrypted response key.
        response_key = f"secrets:{SERVICE_NAME}:{secret_key}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self._redis.get(response_key)
            if raw is not None:
                try:
                    logger.debug(f"[SecretClient] Found response for {secret_key}")
                    response = json.loads(raw)
                    plaintext = self._decrypt_response(response, totp_code)
                    # Best-effort cleanup – TTL on the key handles the rest.
                    self._redis.delete(response_key)
                    logger.info(f"[SecretClient] Secret '{secret_key}' successfully retrieved and decrypted")
                    return plaintext
                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    logger.error("Failed to decrypt secret '%s': %s", secret_key, exc)
                    return None
                except Exception as exc:  # pylint: disable=broad-except
                    logger.error(
                        "Unexpected error decrypting secret '%s': %s", secret_key, exc
                    )
                    return None
            time.sleep(0.1)

        logger.warning("Secret request timeout: %s", secret_key)
        return None

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _decrypt_response(self, response: dict, totp_code: str) -> str:
        """
        Decrypt an AES-256-GCM encrypted response payload from the Launcher.

        The Launcher encrypts using:
            key  = SHA-256(totp_code)
            iv   = random 12 bytes (base64-encoded in payload)
            aead = AES-256-GCM

        Args:
            response:  Parsed JSON payload from ``secrets:{service}:{key}``.
            totp_code: The same 6-digit code used when the request was sent.

        Returns:
            Decrypted plaintext string.

        Raises:
            KeyError: If required payload fields are missing.
            ValueError: If base64 decoding fails.
            cryptography.exceptions.InvalidTag: If decryption/authentication fails.
        """
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        # Derive 256-bit AES key from TOTP code via SHA-256 (mirrors the TS side).
        key_material: bytes = hashlib.sha256(totp_code.encode()).digest()

        # All binary values are base64-encoded by the TypeScript Launcher.
        iv: bytes = base64.b64decode(response["iv"])
        ciphertext: bytes = base64.b64decode(response["secret"])
        auth_tag: bytes = base64.b64decode(response["auth_tag"])

        # The ``cryptography`` AESGCM API expects ciphertext || auth_tag.
        aesgcm = AESGCM(key_material)
        plaintext_bytes: bytes = aesgcm.decrypt(iv, ciphertext + auth_tag, None)
        return plaintext_bytes.decode("utf-8")
