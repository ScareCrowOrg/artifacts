# Shared Tests

Unit tests for shared canonical utilities, covering the BaseService heartbeat and Redis client job routing logic.

## Purpose

This directory validates the shared utilities used across all ScareVerse canonical services:
- **BaseService tests**: Validates Redis key format, TTL, heartbeat loop behavior, error handling, and port health checking
- **Redis client tests**: Validates capability-based job routing (L1 vs L2 selection based on GateKeeper serving capabilities)

## Directory Structure

```
tests/
├── __init__.py              - Python package marker
├── test_base_service.py     - Tests for BaseService Redis heartbeat registration
└── test_redis_client.py     - Tests for capability-based job routing (L1 vs L2)
```

## How to Use

```bash
# Run from the canonical/shared root
cd artifacts/canonical/shared
pytest tests/ -v

# Run a specific test module
pytest tests/test_base_service.py -v
```

## Content Index

| File | Description |
|---|---|
| `__init__.py` | Python package marker |
| `test_base_service.py` | Tests for heartbeat key format, TTL, loop, error recovery, and port health |
| `test_redis_client.py` | Tests for capability checks and L1/L2 routing decisions |
