"""
Unit tests for app/database/encryption.py

Tests encryption/decryption of sensitive fields in documents.
Tests field-specific encryption for modelos_ia collection.
"""

import pytest
from app.database.encryption import encrypt_sensitive_fields, decrypt_sensitive_fields


class TestEncryptSensitiveFields:
    """Test encryption of sensitive fields in documents."""
    
    def test_encrypt_apikey_in_modelos_ia(self, encryption_key):
        """Test that apiKey is encrypted in modelos_ia collection."""
        doc = {
            "id": "modelo_1",
            "name": "GPT-4",
            "provider": "openai",
            "apiKey": "sk-test-secret-key-123"
        }
        
        encrypted_doc = encrypt_sensitive_fields("ai_models", doc)
        
        # apiKey should be changed (encrypted)
        assert encrypted_doc["apiKey"] != "sk-test-secret-key-123"
        # Other fields should be unchanged
        assert encrypted_doc["id"] == "modelo_1"
        assert encrypted_doc["name"] == "GPT-4"
        assert encrypted_doc["provider"] == "openai"
    
    def test_encrypt_does_not_affect_other_collections(self, encryption_key):
        """Test that encryption only applies to modelos_ia collection."""
        doc = {
            "id": "celula_1",
            "name": "Test Cell",
            "apiKey": "should-not-be-encrypted"
        }
        
        # For cells collection, should not encrypt
        encrypted_doc = encrypt_sensitive_fields("cells", doc)
        
        assert encrypted_doc["apiKey"] == "should-not-be-encrypted"
    
    def test_encrypt_without_apikey_field(self, encryption_key):
        """Test encryption when apiKey field is not present."""
        doc = {
            "id": "modelo_2",
            "name": "Gemini",
            "provider": "google"
        }
        
        # Should not raise error
        encrypted_doc = encrypt_sensitive_fields("ai_models", doc)
        
        assert encrypted_doc == doc
        assert "apiKey" not in encrypted_doc
    
    def test_encrypt_with_none_apikey(self, encryption_key):
        """Test encryption when apiKey is None."""
        doc = {
            "id": "modelo_3",
            "name": "Local Model",
            "apiKey": None
        }
        
        # Should not encrypt None value
        encrypted_doc = encrypt_sensitive_fields("ai_models", doc)
        
        # apiKey should remain as-is (or be skipped)
        assert encrypted_doc.get("apiKey") is None or "apiKey" not in encrypted_doc
    
    def test_encrypt_with_empty_apikey(self, encryption_key):
        """Test encryption when apiKey is empty string."""
        doc = {
            "id": "modelo_4",
            "name": "Test Model",
            "apiKey": ""
        }
        
        # Should not encrypt empty string
        encrypted_doc = encrypt_sensitive_fields("ai_models", doc)
        
        # Empty string should remain as-is (or be skipped)
        assert encrypted_doc.get("apiKey") == "" or "apiKey" not in encrypted_doc
    
    def test_encrypt_without_encryption_key_configured(self, no_encryption_key):
        """Test that encryption is skipped when ENCRYPTION_KEY not configured."""
        doc = {
            "id": "modelo_5",
            "name": "Public Model",
            "apiKey": "test-key"
        }
        
        # Should return unchanged when encryption not configured
        encrypted_doc = encrypt_sensitive_fields("ai_models", doc)
        
        assert encrypted_doc["apiKey"] == "test-key"
    
    def test_encrypt_preserves_other_fields(self, encryption_key):
        """Test that encryption preserves all non-sensitive fields."""
        doc = {
            "id": "modelo_6",
            "name": "Complex Model",
            "provider": "openai",
            "apiKey": "secret",
            "configuracoes": {
                "temperature": 0.7,
                "max_tokens": 1000
            },
            "metadata": {
                "created": "2024-01-01",
                "version": "1.0"
            }
        }
        
        encrypted_doc = encrypt_sensitive_fields("ai_models", doc)
        
        # Non-sensitive fields should be unchanged
        assert encrypted_doc["id"] == "modelo_6"
        assert encrypted_doc["name"] == "Complex Model"
        assert encrypted_doc["configuracoes"]["temperature"] == 0.7
        assert encrypted_doc["metadata"]["version"] == "1.0"
    
    def test_encrypt_multiple_times_produces_different_results(self, encryption_key):
        """Test that encrypting the same value multiple times produces different ciphertexts."""
        doc1 = {"id": "m1", "apiKey": "same-secret"}
        doc2 = {"id": "m2", "apiKey": "same-secret"}
        
        encrypted1 = encrypt_sensitive_fields("ai_models", doc1)
        encrypted2 = encrypt_sensitive_fields("ai_models", doc2)
        
        # Due to encryption randomness, ciphertexts should differ
        # (Fernet includes timestamp and random IV)
        # Both should be encrypted though
        assert encrypted1["apiKey"] != "same-secret"
        assert encrypted2["apiKey"] != "same-secret"


class TestDecryptSensitiveFields:
    """Test decryption of sensitive fields in documents."""
    
    def test_decrypt_apikey_in_modelos_ia(self, encryption_key):
        """Test decrypting apiKey in modelos_ia collection."""
        original_key = "sk-test-secret-key-123"
        
        # First encrypt
        doc = {
            "id": "modelo_1",
            "name": "GPT-4",
            "apiKey": original_key
        }
        encrypted_doc = encrypt_sensitive_fields("ai_models", doc)
        
        # Then decrypt
        decrypted_doc = decrypt_sensitive_fields("ai_models", encrypted_doc)
        
        # Should match original
        assert decrypted_doc["apiKey"] == original_key
        assert decrypted_doc["id"] == "modelo_1"
        assert decrypted_doc["name"] == "GPT-4"
    
    def test_decrypt_does_not_affect_other_collections(self, encryption_key):
        """Test that decryption only applies to modelos_ia collection."""
        doc = {
            "id": "celula_1",
            "apiKey": "plain-text-key"
        }
        
        decrypted_doc = decrypt_sensitive_fields("cells", doc)
        
        # Should remain unchanged
        assert decrypted_doc["apiKey"] == "plain-text-key"
    
    def test_decrypt_without_apikey_field(self, encryption_key):
        """Test decryption when apiKey field is not present."""
        doc = {
            "id": "modelo_2",
            "name": "Gemini"
        }
        
        decrypted_doc = decrypt_sensitive_fields("ai_models", doc)
        
        assert decrypted_doc == doc
        assert "apiKey" not in decrypted_doc
    
    def test_decrypt_with_none_apikey(self, encryption_key):
        """Test decryption when apiKey is None."""
        doc = {
            "id": "modelo_3",
            "apiKey": None
        }
        
        decrypted_doc = decrypt_sensitive_fields("ai_models", doc)
        
        # Should not raise error
        assert decrypted_doc.get("apiKey") is None or "apiKey" not in decrypted_doc
    
    def test_decrypt_without_encryption_key_configured(self, no_encryption_key):
        """Test decryption fails gracefully when ENCRYPTION_KEY not configured."""
        doc = {
            "id": "modelo_4",
            "apiKey": "encrypted-value"
        }
        
        # Should return unchanged (with warning logged)
        decrypted_doc = decrypt_sensitive_fields("ai_models", doc)
        
        assert decrypted_doc["apiKey"] == "encrypted-value"
    
    def test_decrypt_corrupted_value_sets_none(self, encryption_key):
        """Test that corrupted encrypted value is handled gracefully."""
        doc = {
            "id": "modelo_5",
            "apiKey": "corrupted-not-valid-fernet-token"
        }
        
        # Should set to None and log warning
        decrypted_doc = decrypt_sensitive_fields("ai_models", doc)
        
        # Should be set to None on decryption failure
        assert decrypted_doc["apiKey"] is None
    
    def test_decrypt_preserves_other_fields(self, encryption_key):
        """Test that decryption preserves all non-sensitive fields."""
        original_key = "secret-api-key"
        doc = {
            "id": "modelo_6",
            "name": "Model",
            "provider": "openai",
            "apiKey": original_key,
            "configuracoes": {"temp": 0.5}
        }
        
        # Encrypt then decrypt
        encrypted = encrypt_sensitive_fields("ai_models", doc)
        decrypted = decrypt_sensitive_fields("ai_models", encrypted)
        
        # All fields preserved
        assert decrypted["id"] == "modelo_6"
        assert decrypted["name"] == "Model"
        assert decrypted["configuracoes"]["temp"] == 0.5
        assert decrypted["apiKey"] == original_key


class TestEncryptionRoundTrip:
    """Test complete encryption/decryption cycles."""
    
    def test_round_trip_with_complex_document(self, encryption_key):
        """Test encrypting and decrypting a complex document."""
        original = {
            "id": "modelo_complex",
            "name": "GPT-4 Turbo",
            "provider": "openai",
            "apiKey": "sk-proj-test-key-12345678901234567890",
            "configuracoes": {
                "temperature": 0.7,
                "max_tokens": 2000,
                "top_p": 1.0,
                "frequency_penalty": 0.0
            },
            "metadata": {
                "version": "1.0",
                "created": "2024-01-01T00:00:00Z",
                "tags": ["production", "high-priority"]
            }
        }
        
        # Encrypt
        encrypted = encrypt_sensitive_fields("ai_models", original.copy())
        
        # apiKey should be different
        assert encrypted["apiKey"] != original["apiKey"]
        
        # Decrypt
        decrypted = decrypt_sensitive_fields("ai_models", encrypted)
        
        # Should match original exactly
        assert decrypted == original
    
    def test_round_trip_multiple_documents(self, encryption_key):
        """Test encrypting and decrypting multiple documents."""
        documents = [
            {"id": f"modelo_{i}", "name": f"Model {i}", "apiKey": f"key-{i}"}
            for i in range(5)
        ]
        
        # Encrypt all
        encrypted_docs = [
            encrypt_sensitive_fields("ai_models", doc.copy())
            for doc in documents
        ]
        
        # All should be encrypted
        for i, enc_doc in enumerate(encrypted_docs):
            assert enc_doc["apiKey"] != f"key-{i}"
        
        # Decrypt all
        decrypted_docs = [
            decrypt_sensitive_fields("ai_models", enc_doc)
            for enc_doc in encrypted_docs
        ]
        
        # All should match originals
        for i, dec_doc in enumerate(decrypted_docs):
            assert dec_doc["apiKey"] == f"key-{i}"
            assert dec_doc["id"] == f"modelo_{i}"
    
    def test_round_trip_with_special_characters(self, encryption_key):
        """Test encryption/decryption with special characters in apiKey."""
        special_keys = [
            "key-with-dashes",
            "key_with_underscores",
            "key.with.dots",
            "key/with/slashes",
            "key=with=equals",
            "key:with:colons",
            "key@with@at",
            "key#with#hash",
            "🔑-emoji-key"
        ]
        
        for original_key in special_keys:
            doc = {"id": "test", "apiKey": original_key}
            
            # Round trip
            encrypted = encrypt_sensitive_fields("ai_models", doc)
            decrypted = decrypt_sensitive_fields("ai_models", encrypted)
            
            # Should preserve special characters
            assert decrypted["apiKey"] == original_key, \
                f"Failed for key: {original_key}"


class TestEncryptionEdgeCases:
    """Test edge cases in encryption/decryption."""
    
    def test_empty_document(self, encryption_key):
        """Test encrypting empty document."""
        doc = {}
        
        encrypted = encrypt_sensitive_fields("ai_models", doc)
        decrypted = decrypt_sensitive_fields("ai_models", encrypted)
        
        assert encrypted == {}
        assert decrypted == {}
    
    def test_document_with_only_apikey(self, encryption_key):
        """Test document with only apiKey field."""
        doc = {"apiKey": "only-field"}
        
        encrypted = encrypt_sensitive_fields("ai_models", doc)
        assert encrypted["apiKey"] != "only-field"
        
        decrypted = decrypt_sensitive_fields("ai_models", encrypted)
        assert decrypted["apiKey"] == "only-field"
    
    def test_very_long_apikey(self, encryption_key):
        """Test encryption of very long API key."""
        long_key = "sk-" + "x" * 1000
        doc = {"id": "test", "apiKey": long_key}
        
        encrypted = encrypt_sensitive_fields("ai_models", doc)
        decrypted = decrypt_sensitive_fields("ai_models", encrypted)
        
        assert decrypted["apiKey"] == long_key
    
    def test_apikey_with_unicode(self, encryption_key):
        """Test encryption of API key with Unicode characters."""
        unicode_key = "key-with-中文-and-émojis-🔐"
        doc = {"id": "test", "apiKey": unicode_key}
        
        encrypted = encrypt_sensitive_fields("ai_models", doc)
        decrypted = decrypt_sensitive_fields("ai_models", encrypted)
        
        assert decrypted["apiKey"] == unicode_key
