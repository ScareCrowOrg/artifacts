"""
Crypto utilities for encrypting/decrypting sensitive data.

This module provides secure encryption/decryption for sensitive fields like API keys
using Fernet symmetric encryption (AES-128 in CBC mode with HMAC authentication).
"""

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

from .config import ENCRYPTION_KEY

logger = logging.getLogger(__name__)


def _get_cipher() -> Fernet:
    """
    Get or initialize the Fernet cipher.
    Reads ENCRYPTION_KEY from config.py (which already uses env), for centralization.
    Returns:
        Fernet cipher instance
    Raises:
        ValueError: If ENCRYPTION_KEY is not configured
    """
    encryption_key = ENCRYPTION_KEY or os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        raise ValueError(
            "ENCRYPTION_KEY not configured. Please set ENCRYPTION_KEY in .env file or config.py. "
            'Generate a key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(encryption_key.encode())
    except Exception as e:
        raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}") from e


def encrypt_value(value: str) -> str:
    """
    Encrypt a string value using Fernet symmetric encryption.

    Args:
        value: Plain text string to encrypt

    Returns:
        Encrypted string (base64-encoded)

    Raises:
        ValueError: If ENCRYPTION_KEY is not configured

    Example:
        >>> encrypted = encrypt_value("my-secret-api-key")
        >>> # Returns something like: "gAAAAABhN..."
    """
    if not value:
        return value

    cipher = _get_cipher()
    encrypted_bytes = cipher.encrypt(value.encode())
    return encrypted_bytes.decode()


def decrypt_value(encrypted_value: str) -> str:
    """
    Decrypt a Fernet-encrypted string value.

    Args:
        encrypted_value: Encrypted string (base64-encoded)

    Returns:
        Decrypted plain text string

    Raises:
        ValueError: If ENCRYPTION_KEY is not configured or value cannot be decrypted

    Example:
        >>> decrypted = decrypt_value("gAAAAABhN...")
        >>> # Returns: "my-secret-api-key"
    """
    if not encrypted_value:
        return encrypted_value

    cipher = _get_cipher()

    try:
        decrypted_bytes = cipher.decrypt(encrypted_value.encode())
        return decrypted_bytes.decode()
    except InvalidToken:
        logger.error("Failed to decrypt value: invalid token or corrupted data")
        raise ValueError(
            "Failed to decrypt value: invalid encryption key or corrupted data"
        )
    except Exception as e:
        logger.error("Failed to decrypt value: %s", e)
        raise ValueError(f"Failed to decrypt value: {e}") from e


def is_encryption_configured() -> bool:
    """
    Check if encryption is properly configured.

    Returns:
        True if ENCRYPTION_KEY is set and valid, False otherwise
    """
    try:
        _get_cipher()
        return True
    except ValueError:
        return False
