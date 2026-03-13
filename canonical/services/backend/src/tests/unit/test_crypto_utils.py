"""
Unit tests for crypto_utils module.

Tests encryption/decryption utilities including:
- Fernet cipher initialization
- Value encryption and decryption
- Error handling for invalid keys and corrupted data
- Configuration validation
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet, InvalidToken

from app.crypto_utils import (
    _get_cipher,
    encrypt_value,
    decrypt_value,
    is_encryption_configured,
)


# Test encryption key (valid Fernet key format)
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


class TestGetCipher:
    """Tests for _get_cipher utility function."""
    
    def test_get_cipher_with_valid_key(self):
        """Test getting cipher with valid encryption key."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            cipher = _get_cipher()
            assert isinstance(cipher, Fernet)
    
    def test_get_cipher_without_config_key_uses_env(self):
        """Test that cipher falls back to environment variable."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", None), \
             patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_ENCRYPTION_KEY}):
            cipher = _get_cipher()
            assert isinstance(cipher, Fernet)
    
    def test_get_cipher_raises_error_when_key_missing(self):
        """Test that cipher raises error when key is not configured."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", None), \
             patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                _get_cipher()
            
            assert "ENCRYPTION_KEY not configured" in str(exc_info.value)
    
    def test_get_cipher_raises_error_with_invalid_key_format(self):
        """Test that cipher raises error with invalid key format."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", "invalid-key-format"):
            with pytest.raises(ValueError) as exc_info:
                _get_cipher()
            
            assert "Invalid ENCRYPTION_KEY format" in str(exc_info.value)
    
    def test_get_cipher_with_short_key(self):
        """Test that cipher rejects keys that are too short."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", "short"):
            with pytest.raises(ValueError):
                _get_cipher()


class TestEncryptValue:
    """Tests for encrypt_value function."""
    
    def test_encrypt_value_returns_encrypted_string(self):
        """Test that encrypt_value returns an encrypted string."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            plaintext = "my-secret-api-key"
            encrypted = encrypt_value(plaintext)
            
            assert encrypted != plaintext
            assert isinstance(encrypted, str)
            assert len(encrypted) > 0
    
    def test_encrypt_value_produces_different_output_each_time(self):
        """Test that encrypting the same value produces different output (due to IV)."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            plaintext = "test-value"
            encrypted1 = encrypt_value(plaintext)
            encrypted2 = encrypt_value(plaintext)
            
            # Should be different due to random initialization vector
            assert encrypted1 != encrypted2
    
    def test_encrypt_value_with_empty_string(self):
        """Test encrypting empty string returns empty string."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            encrypted = encrypt_value("")
            assert encrypted == ""
    
    def test_encrypt_value_with_none(self):
        """Test encrypting None returns None."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            encrypted = encrypt_value(None)
            assert encrypted is None
    
    def test_encrypt_value_with_unicode_characters(self):
        """Test encrypting value with unicode characters."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            plaintext = "Señor José's API Key ñáéíóú 中文"
            encrypted = encrypt_value(plaintext)
            
            assert encrypted != plaintext
            assert isinstance(encrypted, str)
    
    def test_encrypt_value_with_special_characters(self):
        """Test encrypting value with special characters."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            plaintext = "key!@#$%^&*()[]{}|;':,.<>?/~`"
            encrypted = encrypt_value(plaintext)
            
            assert encrypted != plaintext
    
    def test_encrypt_value_raises_error_without_key(self):
        """Test that encrypt_value raises error when key is not configured."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", None), \
             patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                encrypt_value("test")
            
            assert "ENCRYPTION_KEY not configured" in str(exc_info.value)


class TestDecryptValue:
    """Tests for decrypt_value function."""
    
    def test_decrypt_value_returns_original_plaintext(self):
        """Test that decrypt_value correctly decrypts encrypted value."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            plaintext = "my-secret-api-key"
            encrypted = encrypt_value(plaintext)
            decrypted = decrypt_value(encrypted)
            
            assert decrypted == plaintext
    
    def test_decrypt_value_with_unicode_characters(self):
        """Test decrypting value with unicode characters."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            plaintext = "Señor José's API Key ñáéíóú 中文"
            encrypted = encrypt_value(plaintext)
            decrypted = decrypt_value(encrypted)
            
            assert decrypted == plaintext
    
    def test_decrypt_value_with_empty_string(self):
        """Test decrypting empty string returns empty string."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            decrypted = decrypt_value("")
            assert decrypted == ""
    
    def test_decrypt_value_with_none(self):
        """Test decrypting None returns None."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            decrypted = decrypt_value(None)
            assert decrypted is None
    
    def test_decrypt_value_raises_error_with_invalid_token(self):
        """Test that decrypt_value raises error for invalid encrypted token."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            with pytest.raises(ValueError) as exc_info:
                decrypt_value("invalid-encrypted-token")
            
            assert "Failed to decrypt value" in str(exc_info.value)
            assert "invalid encryption key or corrupted data" in str(exc_info.value)
    
    def test_decrypt_value_raises_error_with_corrupted_data(self):
        """Test that decrypt_value raises error for corrupted encrypted data."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            # Create a valid encrypted value then corrupt it
            plaintext = "test"
            encrypted = encrypt_value(plaintext)
            corrupted = encrypted[:-5] + "xxxxx"  # Corrupt the end
            
            with pytest.raises(ValueError) as exc_info:
                decrypt_value(corrupted)
            
            assert "Failed to decrypt value" in str(exc_info.value)
    
    def test_decrypt_value_with_wrong_key(self):
        """Test that decrypt_value fails when using wrong encryption key."""
        # Encrypt with one key
        key1 = Fernet.generate_key().decode()
        with patch("app.crypto_utils.ENCRYPTION_KEY", key1):
            encrypted = encrypt_value("secret")
        
        # Try to decrypt with different key
        key2 = Fernet.generate_key().decode()
        with patch("app.crypto_utils.ENCRYPTION_KEY", key2):
            with pytest.raises(ValueError) as exc_info:
                decrypt_value(encrypted)
            
            assert "Failed to decrypt value" in str(exc_info.value)
    
    def test_decrypt_value_raises_error_without_key(self):
        """Test that decrypt_value raises error when key is not configured."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", None), \
             patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                decrypt_value("some-encrypted-value")
            
            assert "ENCRYPTION_KEY not configured" in str(exc_info.value)


class TestIsEncryptionConfigured:
    """Tests for is_encryption_configured function."""
    
    def test_returns_true_with_valid_key(self):
        """Test that is_encryption_configured returns True with valid key."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            assert is_encryption_configured() is True
    
    def test_returns_false_without_key(self):
        """Test that is_encryption_configured returns False without key."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", None), \
             patch.dict(os.environ, {}, clear=True):
            assert is_encryption_configured() is False
    
    def test_returns_false_with_invalid_key(self):
        """Test that is_encryption_configured returns False with invalid key."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", "invalid-key"):
            assert is_encryption_configured() is False
    
    def test_returns_true_with_env_key(self):
        """Test that is_encryption_configured returns True with environment key."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", None), \
             patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_ENCRYPTION_KEY}):
            assert is_encryption_configured() is True


class TestEncryptionDecryptionRoundTrip:
    """Integration tests for encryption/decryption round trips."""
    
    def test_round_trip_preserves_data(self):
        """Test that encrypt then decrypt returns original data."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            test_values = [
                "simple-string",
                "string with spaces",
                "123456",
                "special!@#$%^&*()",
                "unicode: ñáéíóú 中文 日本語",
                "a" * 1000,  # Long string
            ]
            
            for value in test_values:
                encrypted = encrypt_value(value)
                decrypted = decrypt_value(encrypted)
                assert decrypted == value
    
    def test_multiple_encryptions_all_decrypt_correctly(self):
        """Test that multiple encrypted values can all be decrypted."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            test_data = {
                "api_key_1": "sk_live_abc123",
                "api_key_2": "sk_test_xyz789",
                "password": "super-secret-password",
            }
            
            encrypted_data = {
                key: encrypt_value(value)
                for key, value in test_data.items()
            }
            
            decrypted_data = {
                key: decrypt_value(value)
                for key, value in encrypted_data.items()
            }
            
            assert decrypted_data == test_data
    
    def test_encrypted_data_is_different_from_plaintext(self):
        """Test that encrypted data doesn't contain plaintext."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY):
            plaintext = "very-secret-api-key"
            encrypted = encrypt_value(plaintext)
            
            # Encrypted value should not contain the plaintext
            assert plaintext not in encrypted
            
            # But should decrypt correctly
            assert decrypt_value(encrypted) == plaintext


class TestErrorHandlingAndLogging:
    """Tests for error handling and logging behavior."""
    
    def test_decrypt_logs_error_on_invalid_token(self):
        """Test that decrypt_value logs error for invalid token."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY), \
             patch("app.crypto_utils.logger") as mock_logger:
            
            with pytest.raises(ValueError):
                decrypt_value("invalid-token")
            
            # Verify error was logged
            mock_logger.error.assert_called()
            error_message = mock_logger.error.call_args[0][0]
            assert "Failed to decrypt value" in error_message
    
    def test_decrypt_logs_error_on_exception(self):
        """Test that decrypt_value logs error on general exception."""
        with patch("app.crypto_utils.ENCRYPTION_KEY", TEST_ENCRYPTION_KEY), \
             patch("app.crypto_utils.logger") as mock_logger:
            
            # Try to decrypt invalid base64
            with pytest.raises(ValueError):
                decrypt_value("not-base64!!!")
            
            # Verify error was logged
            mock_logger.error.assert_called()
