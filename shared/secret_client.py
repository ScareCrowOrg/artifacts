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
REDIS_PASSWORD: str = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
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
            password=REDIS_PASSWORD,
            decode_responses=False,
        )
        logger.info(f"[SecretClient] Connected to Redis L1 at {REDIS_HOST}:{REDIS_PORT} (with auth)")

    def request_secret(self, secret_key: str, timeout: int = 60) -> Optional[str]:
        """
        Request a secret from the Launcher.

        Publishes a TOTP-authenticated request to Redis and polls for the
        encrypted response.  On success the secret is decrypted, the Redis
        key is deleted (best-effort), and the plaintext is returned.

        Args:
            secret_key: Logical name of the secret (e.g. ``"redis-password"``).
            timeout:    Maximum seconds to wait for the Launcher's response (default: 60s).

        Returns:
            Decrypted plaintext secret string, or ``None`` if the request
            timed out or the Launcher rejected it.
        """
        request_id = f"{SERVICE_NAME}:{secret_key}"
        start_time = time.time()

        logger.info(f"[SecretClient] ▶️ START requesting secret: {request_id} (timeout: {timeout}s)")

        # STEP 1: Publish request to Redis
        logger.debug(f"[SecretClient] [{request_id}] Step 1: Building request payload")
        request_payload = json.dumps(
            {
                "service": SERVICE_NAME,
                "secret_key": secret_key,
            }
        )
        request_channel = f"request:secret:{SERVICE_NAME}:{secret_key}"
        logger.debug(f"[SecretClient] [{request_id}] Request payload: {request_payload}")

        try:
            logger.debug(f"[SecretClient] [{request_id}] Step 2: Publishing request to Redis at key '{request_channel}'")
            self._redis.setex(request_channel, 60, request_payload)
            logger.debug(f"[SecretClient] [{request_id}] ✅ STEP 2 OK: Request published (TTL: 60s)")
            logger.info(f"[DIAG] SecretClient: Publishing request for key={secret_key} ttl=60s")
        except Exception as e:
            logger.info(f"[DIAG] SecretClient: Returning None for key={secret_key} after {time.time() - start_time:.1f}s — Redis setex failed")
            logger.error(f"[SecretClient] [{request_id}] ❌ STEP 2 FAILED: Could not publish request to Redis")
            logger.error(f"[SecretClient] [{request_id}] Error: {type(e).__name__}: {str(e)}")
            return None

        # STEP 3: Poll for response
        logger.debug(f"[SecretClient] [{request_id}] Step 3: Starting poll loop (100ms interval)")
        response_key = f"secrets:{SERVICE_NAME}:{secret_key}"
        deadline = time.time() + timeout
        poll_count = 0

        while time.time() < deadline:
            poll_count += 1
            remaining = deadline - time.time()

            try:
                raw = self._redis.get(response_key)
            except Exception as e:
                logger.info(f"[DIAG] SecretClient: Returning None for key={secret_key} after {time.time() - start_time:.1f}s — Redis read error")
                logger.error(f"[SecretClient] [{request_id}] ❌ Poll cycle {poll_count} FAILED: Redis read error")
                logger.error(f"[SecretClient] [{request_id}] Error: {type(e).__name__}: {str(e)}")
                return None

            if raw is not None:
                poll_elapsed = time.time() - start_time
                logger.info(f"[DIAG] SecretClient: GOT RESPONSE key={secret_key} elapsed={poll_elapsed:.1f}s size={len(raw)}")
                logger.debug(f"[SecretClient] [{request_id}] ✅ Response found after {poll_count} polls (~{poll_elapsed:.1f}s)")
                logger.debug(f"[SecretClient] [{request_id}] Response size: {len(raw)} bytes")

                # STEP 4: Parse response JSON
                logger.debug(f"[SecretClient] [{request_id}] Step 4: Parsing response JSON")
                try:
                    response = json.loads(raw)
                    logger.debug(f"[SecretClient] [{request_id}] ✅ STEP 4 OK: JSON parsed successfully")
                    logger.debug(f"[SecretClient] [{request_id}] Response keys: {list(response.keys())}")
                except json.JSONDecodeError as exc:
                    logger.error(f"[SecretClient] [{request_id}] ❌ STEP 4 FAILED: Invalid JSON in response")
                    logger.error(f"[SecretClient] [{request_id}] Raw response: {raw[:200]}...")
                    logger.error(f"[SecretClient] [{request_id}] JSON Error: {str(exc)}")
                    return None
                except Exception as exc:
                    logger.error(f"[SecretClient] [{request_id}] ❌ STEP 4 FAILED: Unexpected error parsing response")
                    logger.error(f"[SecretClient] [{request_id}] Error: {type(exc).__name__}: {str(exc)}")
                    return None

                # STEP 5: Decrypt response
                logger.debug(f"[SecretClient] [{request_id}] Step 5: Decrypting response with AES-256-GCM")
                try:
                    plaintext = self._decrypt_response(response)
                    logger.debug(f"[SecretClient] [{request_id}] ✅ STEP 5 OK: Decryption successful (plaintext length: {len(plaintext)} chars)")
                except KeyError as exc:
                    logger.error(f"[SecretClient] [{request_id}] ❌ STEP 5 FAILED: Missing required field in response")
                    logger.error(f"[SecretClient] [{request_id}] Missing field: {str(exc)}")
                    logger.error(f"[SecretClient] [{request_id}] Available fields: {list(response.keys())}")
                    return None
                except ValueError as exc:
                    logger.error(f"[SecretClient] [{request_id}] ❌ STEP 5 FAILED: Invalid base64 encoding in response")
                    logger.error(f"[SecretClient] [{request_id}] ValueError: {str(exc)}")
                    return None
                except Exception as exc:
                    logger.error(f"[SecretClient] [{request_id}] ❌ STEP 5 FAILED: Decryption error")
                    logger.error(f"[SecretClient] [{request_id}] Error type: {type(exc).__name__}")
                    logger.error(f"[SecretClient] [{request_id}] Error message: {str(exc)}")
                    if hasattr(exc, '__traceback__'):
                        import traceback
                        logger.error(f"[SecretClient] [{request_id}] Traceback: {traceback.format_exc()}")
                    return None

                # STEP 6: Cleanup
                logger.debug(f"[SecretClient] [{request_id}] Step 6: Cleaning up response key from Redis")
                try:
                    self._redis.delete(response_key)
                    logger.debug(f"[SecretClient] [{request_id}] ✅ STEP 6 OK: Response key deleted")
                except Exception as e:
                    logger.warning(f"[SecretClient] [{request_id}] ⚠️ STEP 6 WARNING: Could not delete response key (TTL will handle it)")
                    logger.warning(f"[SecretClient] [{request_id}] Error: {type(e).__name__}: {str(e)}")

                total_elapsed = time.time() - start_time
                logger.info(f"[SecretClient] ✅ SUCCESS: Secret '{secret_key}' retrieved and decrypted ({total_elapsed:.2f}s)")
                logger.info(f"[SecretClient] [{request_id}] Polling took {poll_count} cycles (~{poll_elapsed:.1f}s)")
                # Log first 15 chars of secret for validation (not full value for security)
                secret_preview = plaintext[:15] if len(plaintext) >= 15 else plaintext
                logger.info(f"[SecretClient] [{request_id}] Secret preview (first 15 chars): {secret_preview}...")
                return plaintext

            time.sleep(0.1)
            if poll_count % 10 == 0:  # Log every 10 polls (every 1s)
                logger.debug(f"[SecretClient] [{request_id}] Still polling... ({poll_count} polls, {remaining:.1f}s remaining)")
            if poll_count % 50 == 0:  # Log every 50 polls (every ~5s)
                poll_elapsed = time.time() - start_time
                logger.info(f"[DIAG] SecretClient: Polling key={secret_key} elapsed={poll_elapsed:.1f}s (attempt {poll_count})")

        # Timeout occurred
        total_elapsed = time.time() - start_time
        logger.info(f"[DIAG] SecretClient: TIMEOUT key={secret_key} elapsed={total_elapsed:.1f}s — no response from Launcher")
        logger.error(f"[SecretClient] ❌ TIMEOUT: No response from Launcher after {timeout}s")
        logger.error(f"[SecretClient] [{request_id}] Tried {poll_count} polls across {total_elapsed:.2f}s")
        logger.error(f"[SecretClient] [{request_id}] Expected response key: {response_key}")
        logger.error(f"[SecretClient] [{request_id}] Possible causes:")
        logger.error(f"[SecretClient] [{request_id}]   1. Launcher not running or crashed")
        logger.error(f"[SecretClient] [{request_id}]   2. Orchestrator loop not polling Redis")
        logger.error(f"[SecretClient] [{request_id}]   3. Service seed not registered")
        logger.error(f"[SecretClient] [{request_id}]   4. Network/Redis connectivity issues")
        logger.info(f"[DIAG] SecretClient: Returning None for key={secret_key} elapsed={total_elapsed:.1f}s — timeout")
        return None

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _decrypt_response(self, response: dict) -> str:
        """
        Decrypt an AES-256-GCM encrypted response payload from the Launcher.

        The Launcher encrypts using:
            key  = SHA-256(totp_code)
            iv   = random 12 bytes (base64-encoded in payload)
            aead = AES-256-GCM

        The response includes the timestamp used for TOTP generation on the
        Launcher side, so this client regenerates the same TOTP using that
        timestamp and the service's seed.

        Args:
            response:  Parsed JSON payload from ``secrets:{service}:{key}``.
                      Must include ``timestamp`` (ms) used for encryption.

        Returns:
            Decrypted plaintext string.

        Raises:
            KeyError: If required payload fields are missing.
            ValueError: If base64 decoding fails.
            cryptography.exceptions.InvalidTag: If decryption/authentication fails.
        """
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        decrypt_start = time.time()
        logger.debug("[SecretClient._decrypt] ▶️ START decryption process")

        # Sub-step 1: Extract timestamp
        logger.debug("[SecretClient._decrypt] Sub-step 1: Extracting timestamp from response")
        timestamp_ms = response.get("timestamp")
        if timestamp_ms is None:
            logger.error("[SecretClient._decrypt] ❌ Missing 'timestamp' field in response")
            logger.error("[SecretClient._decrypt] Available fields: " + ", ".join(response.keys()))
            raise KeyError("Response missing 'timestamp' field")
        logger.debug(f"[SecretClient._decrypt] ✅ Timestamp extracted: {timestamp_ms} ms")

        # Sub-step 2: Regenerate TOTP code
        logger.debug("[SecretClient._decrypt] Sub-step 2: Regenerating TOTP code from timestamp")
        try:
            timestamp_sec = timestamp_ms // 1000
            totp_code = self._totp.generate_code(timestamp_sec)
            logger.info(f"[SecretClient._decrypt] ✅ TOTP code regenerated (length: {len(totp_code)} chars)")
            logger.info(f"[SecretClient._decrypt]    Timestamp: {timestamp_ms}ms = {timestamp_sec}s")
            logger.info(f"[SecretClient._decrypt]    TOTP code: {totp_code}")
        except Exception as e:
            logger.error("[SecretClient._decrypt] ❌ Failed to generate TOTP code")
            logger.error(f"[SecretClient._decrypt] Error: {type(e).__name__}: {str(e)}")
            raise

        # Sub-step 3: Derive AES key
        logger.debug("[SecretClient._decrypt] Sub-step 3: Deriving AES-256 key from TOTP code")
        try:
            key_material: bytes = hashlib.sha256(totp_code.encode()).digest()
            logger.debug(f"[SecretClient._decrypt] ✅ Key derived (SHA-256, {len(key_material)} bytes)")
        except Exception as e:
            logger.error("[SecretClient._decrypt] ❌ Failed to derive key")
            logger.error(f"[SecretClient._decrypt] Error: {type(e).__name__}: {str(e)}")
            raise

        # Sub-step 4: Decode base64 components
        logger.debug("[SecretClient._decrypt] Sub-step 4: Decoding base64-encoded components")
        try:
            if "iv" not in response:
                raise KeyError("Missing 'iv' field")
            iv: bytes = base64.b64decode(response["iv"])
            logger.debug(f"[SecretClient._decrypt] ✅ IV decoded ({len(iv)} bytes)")
        except (ValueError, KeyError) as e:
            logger.error("[SecretClient._decrypt] ❌ Failed to decode IV")
            logger.error(f"[SecretClient._decrypt] Error: {type(e).__name__}: {str(e)}")
            raise

        try:
            if "secret" not in response:
                raise KeyError("Missing 'secret' field")
            ciphertext: bytes = base64.b64decode(response["secret"])
            logger.debug(f"[SecretClient._decrypt] ✅ Ciphertext decoded ({len(ciphertext)} bytes)")
        except (ValueError, KeyError) as e:
            logger.error("[SecretClient._decrypt] ❌ Failed to decode ciphertext")
            logger.error(f"[SecretClient._decrypt] Error: {type(e).__name__}: {str(e)}")
            raise

        try:
            if "auth_tag" not in response:
                raise KeyError("Missing 'auth_tag' field")
            auth_tag: bytes = base64.b64decode(response["auth_tag"])
            logger.debug(f"[SecretClient._decrypt] ✅ Auth tag decoded ({len(auth_tag)} bytes)")
        except (ValueError, KeyError) as e:
            logger.error("[SecretClient._decrypt] ❌ Failed to decode auth tag")
            logger.error(f"[SecretClient._decrypt] Error: {type(e).__name__}: {str(e)}")
            raise

        # Sub-step 5: Perform AES-256-GCM decryption
        logger.debug("[SecretClient._decrypt] Sub-step 5: Performing AES-256-GCM decryption")
        try:
            aesgcm = AESGCM(key_material)
            plaintext_bytes: bytes = aesgcm.decrypt(iv, ciphertext + auth_tag, None)
            logger.debug(f"[SecretClient._decrypt] ✅ Decryption successful ({len(plaintext_bytes)} bytes)")
        except Exception as e:
            logger.error("[SecretClient._decrypt] ❌ AES-256-GCM decryption failed")
            logger.error(f"[SecretClient._decrypt] Error type: {type(e).__name__}")
            logger.error(f"[SecretClient._decrypt] Error message: {str(e)}")
            logger.error("[SecretClient._decrypt] Possible causes:")
            logger.error("[SecretClient._decrypt]   1. TOTP code mismatch (clock skew?)")
            logger.error("[SecretClient._decrypt]   2. Ciphertext corruption")
            logger.error("[SecretClient._decrypt]   3. Authentication tag verification failed")
            raise

        # Sub-step 6: Decode to UTF-8 string
        logger.debug("[SecretClient._decrypt] Sub-step 6: Decoding plaintext from UTF-8")
        try:
            plaintext = plaintext_bytes.decode("utf-8")
            decrypt_elapsed = time.time() - decrypt_start
            logger.debug(f"[SecretClient._decrypt] ✅ UTF-8 decode successful ({decrypt_elapsed:.2f}s total)")
            return plaintext
        except UnicodeDecodeError as e:
            logger.error("[SecretClient._decrypt] ❌ Failed to decode plaintext as UTF-8")
            logger.error(f"[SecretClient._decrypt] Error: {str(e)}")
            logger.error(f"[SecretClient._decrypt] Plaintext bytes (first 100): {plaintext_bytes[:100]}")
            raise ValueError(f"Plaintext is not valid UTF-8: {str(e)}")
