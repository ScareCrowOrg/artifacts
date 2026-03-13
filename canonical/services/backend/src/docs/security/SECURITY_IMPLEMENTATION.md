---
processed: true
processed_date: 2025-12-07
themes:
  - security
  - encryption
  - api-keys
  - cryptography
modules:
  - backend
  - security
code_verified: true
dead_docs_found: false
---
# Security Implementation - API Key Encryption

## Overview

This document describes the security implementation for API key storage in the ScareVerse project.

## Problem Statement

Previously, API keys for IA models (especially Gemini) were:
- Stored in plain text in JSON files
- Only available as global configuration
- Not model-specific

This presented security risks and limited flexibility.

## Solution

Implemented Fernet symmetric encryption for API keys with automatic encryption/decryption in the database layer.

## Implementation Details

### Encryption Algorithm

- **Algorithm**: Fernet (symmetric encryption)
- **Underlying**: AES-128 in CBC mode
- **Authentication**: HMAC for data integrity
- **Key Management**: Environment variable `ENCRYPTION_KEY`

### Components

#### 1. crypto_utils.py

Core encryption utilities:
- `encrypt_value(value: str) -> str`: Encrypts a string value
- `decrypt_value(encrypted: str) -> str`: Decrypts an encrypted value
- `is_encryption_configured() -> bool`: Checks if encryption is available

#### 2. database.py

Automatic encryption/decryption:
- `_encrypt_sensitive_fields()`: Encrypts apiKey before saving to JSON
- `_decrypt_sensitive_fields()`: Decrypts apiKey after loading from JSON
- Applied transparently in `insert()`, `update()`, `find_one()`, `find_many()`

#### 3. models.py

Model updates:
- Added optional `apiKey` field to `ModeloIA`
- Added `apiKey` to `CriarModeloIARequest` and `AtualizarModeloIARequest`

#### 4. gemini_service.py

Service integration:
- `chamar_gemini()` accepts optional `api_key` parameter
- `processar_chat_com_gemini()` accepts optional `api_key` parameter
- Model-specific key takes priority over global `GEMINI_API_KEY`

#### 5. chat_router.py

Request handling:
- Extracts `apiKey` from model
- Passes to Gemini service when processing chat

## Security Properties

### ✅ Confidentiality

- API keys are encrypted at rest (in JSON files)
- Encryption key stored separately in environment variables
- Keys only decrypted in memory during processing

### ✅ Integrity

- HMAC authentication ensures encrypted data hasn't been tampered with
- Decryption fails if data is corrupted or modified

### ✅ Key Rotation Support

- Encryption key is read dynamically from environment
- Supports key rotation by:
  1. Decrypting all data with old key
  2. Updating `ENCRYPTION_KEY`
  3. Re-encrypting all data with new key

### ✅ Defense in Depth

- Multiple layers of protection:
  - Environment variable isolation
  - File system permissions
  - Application-level encryption
  - Transport layer security (when APIs are called)

## Configuration

### Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Set in Environment

Add to `.env`:
```env
ENCRYPTION_KEY=your-generated-key-here
```

**⚠️ CRITICAL**: Never commit encryption keys to version control!

## Testing

### Test Coverage

- **test_crypto_utils.py**: 11 tests for encryption/decryption functions
- **test_modelos_ia_encryption.py**: 6 tests for database encryption
- **test_encryption_e2e.py**: 1 end-to-end workflow test

Total: 18 tests covering encryption functionality

### Test Isolation

- Uses pytest fixtures (`encryption_key`, `no_encryption_key`)
- Ensures no environment pollution between tests
- Automatic setup and teardown

## Security Analysis

### CodeQL Findings

**Alert**: `py/clear-text-logging-sensitive-data` (4 instances)
- **Location**: `test_encryption_e2e.py`
- **Severity**: Low
- **Status**: Accepted
- **Justification**: Test file intentionally logs dummy API keys to verify encryption workflow. These are not real credentials.

### No Other Security Issues Found

- No SQL injection risks (uses JSON files, not SQL)
- No XSS vulnerabilities (backend only)
- No CSRF risks (API uses token auth)
- No path traversal (existing protections maintained)

## Best Practices

### ✅ DO

- Generate strong encryption keys using Fernet.generate_key()
- Store encryption keys in secure secret management (AWS Secrets Manager, etc.)
- Use different keys for different environments (dev, staging, prod)
- Rotate keys periodically
- Log decryption failures for monitoring

### ❌ DON'T

- Commit encryption keys to version control
- Use weak or predictable keys
- Share keys between environments
- Expose keys in logs or error messages
- Store keys in plain text files

## Migration Path

For existing systems with plain text API keys:

1. Generate encryption key
2. Set `ENCRYPTION_KEY` in environment
3. Read all existing models
4. Update each model (triggers encryption)
5. Verify encrypted values in JSON files
6. Test decryption by reading models

## Future Enhancements

Potential improvements:

1. **Key Rotation Automation**: Automated script to rotate keys
2. **Multiple Key Support**: Support for key versioning
3. **Hardware Security Modules**: Integration with HSM for key management
4. **Audit Logging**: Log all encryption/decryption operations
5. **Per-User Keys**: User-specific encryption keys for BYOK

## Documentation

- [README_CRYPTO.md](app/README_CRYPTO.md) - User guide for encryption utilities
- [SCHEMA.md](../artifacts/canonical/ai_models/SCHEMA.md) - ModeloIA schema with apiKey
- [README.md](../artifacts/canonical/ai_models/README.md) - Security section

## References

- [cryptography.io - Fernet](https://cryptography.io/en/latest/fernet/)
- [OWASP Cryptographic Storage Cheat Sheet](https://owasp.org/www-project-cheat-sheets/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [NIST Special Publication 800-57](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)

---

**Implementation Date**: November 2024  
**Version**: 1.0  
**Status**: ✅ Complete and Tested
