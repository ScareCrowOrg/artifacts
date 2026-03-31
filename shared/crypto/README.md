# Shared Crypto Utilities

Cryptographic helper modules shared across ScareVerseLab backend services.
Provides TOTP (Time-based One-Time Password) validation as a reusable utility
so that individual services do not duplicate OTP logic.

## Purpose

Centralises secret-key-based TOTP validation to enforce consistent security
behaviour across all backend services that need two-factor or service-to-service
authentication.

## Content Index

| File | Description |
|------|-------------|
| `__init__.py` | Package marker; re-exports `TOTPValidator` |
| `totp_validator.py` | `TOTPValidator` class — validates TOTP codes against a shared secret using the RFC 6238 algorithm |

## Related Documentation

- [Shared Artifacts](../README.md) — parent shared utilities directory
- [Backend Auth](../../../backend/docs/) — authentication flow documentation
- [JWT Utilities](../jwt_utils.py) — complementary JWT helper in shared root
