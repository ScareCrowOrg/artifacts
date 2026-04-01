# Shared Tests

Unit tests for shared Python utilities in the ScareVerseLab platform.

## Purpose

This directory contains the Python test suite for the shared backend utilities located in `artifacts/shared/`. These tests validate configuration loading, secret management, and JWT helpers that are used by all Python worker services.

## Index

### Files

| File | Description |
|------|-------------|
| `__init__.py` | Python package marker — makes this directory importable by pytest |
| `test_config_manager.py` | Unit tests for `config_manager.py`; covers Redis-backed config, vault secret routing, in-memory caching (60 s TTL), cache invalidation, and `os.getenv` fallback |

## Running the Tests

From the repository root:

```bash
# Run only the shared tests
pytest artifacts/shared/tests/ -v

# Run with coverage report
pytest artifacts/shared/tests/ --cov=artifacts/shared --cov-report=term-missing
```

From within this directory:

```bash
pytest -v
```

## Test Coverage Areas

The test suite covers the following scenarios in `config_manager.py`:

| Scenario | Status |
|----------|--------|
| `get_config()` with `vault.*` prefix routes to `SecretClient` | ✅ |
| `get_config()` with regular key reads from Redis `settings:{key}` | ✅ |
| In-memory cache (60 s TTL) is populated and returned on second call | ✅ |
| Cache is bypassed for `vault.*` keys (secrets never cached) | ✅ |
| Fallback to `os.getenv` when Redis is unavailable | ✅ |
| Fallback to `os.getenv` when `SecretClient` is unavailable | ✅ |
| Returns `None` when key is absent from all sources | ✅ |
| `clear_cache()` flushes the in-memory store | ✅ |

## Related Documentation

- [Shared Artifacts Root](../) - Overview of all shared artifacts
- [Config Manager](../config_manager.py) - The module under test
- [Secret Client](../secret_client.py) - Secret retrieval client used by config manager
