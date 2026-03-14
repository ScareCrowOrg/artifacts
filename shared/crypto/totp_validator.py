"""
TOTP Validator – Generate and validate time-based one-time passwords.

Used by services to generate TOTP codes when requesting secrets from the
Launcher.  The TOTP seed is received via the ``TOTP_SEED`` environment variable
injected by the Launcher's ServiceOrchestrator during service startup.

Algorithm: RFC 4226 (HOTP) + RFC 6238 (TOTP) with HMAC-SHA1.
Time step: 30 seconds.
Code length: 6 digits (zero-padded).
"""

import hmac
import hashlib
import struct
import time
from typing import Optional


class TOTPValidator:
    """Time-based one-time password generator and validator."""

    TIME_STEP = 30  # seconds per TOTP window
    TOTP_DIGITS = 6  # number of decimal digits in each code

    def __init__(self, seed: str) -> None:
        """
        Initialise with a TOTP seed.

        Args:
            seed: Hex-encoded 32-byte seed (64 hex characters) as provided
                  by the Launcher via the ``TOTP_SEED`` environment variable.

        Raises:
            ValueError: If *seed* is not a valid hex string.
        """
        self.seed_bytes = bytes.fromhex(seed)

    def generate_code(self, timestamp: Optional[int] = None) -> str:
        """
        Generate a TOTP code for the given (or current) time window.

        Args:
            timestamp: Unix timestamp in seconds.  Defaults to the current
                       wall-clock time when not provided.

        Returns:
            A zero-padded 6-digit string, e.g. ``"042731"``.
        """
        if timestamp is None:
            timestamp = int(time.time())

        # TOTP counter = floor(timestamp / TIME_STEP)
        counter = timestamp // self.TIME_STEP

        # HMAC-SHA1(seed, big-endian 8-byte counter)
        message = struct.pack(">Q", counter)
        hash_value = hmac.new(self.seed_bytes, message, hashlib.sha1).digest()

        # Dynamic truncation (RFC 4226 §5.3)
        offset = hash_value[-1] & 0x0F
        (code,) = struct.unpack(">I", hash_value[offset : offset + 4])
        code = code & 0x7FFFFFFF
        code = code % (10 ** self.TOTP_DIGITS)

        return str(code).zfill(self.TOTP_DIGITS)

    def validate_code(
        self,
        code: str,
        timestamp: Optional[int] = None,
        window: int = 1,
    ) -> bool:
        """
        Validate a TOTP code against the current (or given) time window.

        Accepts codes from the current window and up to *window* adjacent
        windows on each side to tolerate minor clock skew between caller and
        Launcher.

        Args:
            code:      6-digit TOTP code string to validate.
            timestamp: Unix timestamp in seconds to validate against.
                       Defaults to the current wall-clock time.
            window:    Number of adjacent time steps to accept on each side
                       (default 1 = ±30 s).

        Returns:
            ``True`` if *code* matches any accepted window, ``False`` otherwise.
        """
        if timestamp is None:
            timestamp = int(time.time())

        counter = timestamp // self.TIME_STEP
        for offset in range(-window, window + 1):
            expected = self.generate_code((counter + offset) * self.TIME_STEP)
            # Constant-time comparison to prevent timing attacks.
            if hmac.compare_digest(code, expected):
                return True

        return False
