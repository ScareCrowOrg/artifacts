# Traefik Service Tests

Unit tests for the Traefik service integration — covering heartbeat registration and Redis-based service discovery.

## Purpose

This directory validates the Traefik service's integration with the ScareVerse infrastructure:
- **Heartbeat tests**: Ensures the service registers correctly with Redis L1 using the expected service name and handles import errors gracefully
- **Service discovery tests**: Validates the Redis SCAN-based service discovery daemon that builds Traefik routing configuration dynamically

## Directory Structure

```
tests/
├── __init__.py                  - Python package marker
├── conftest.py                  - Shared pytest fixtures
├── test_heartbeat.py            - Tests for heartbeat Redis registration
└── test_service_discovery.py    - Tests for the Redis L1 service discovery daemon
```

## How to Use

```bash
# Run from the traefik service root
cd artifacts/canonical/services/traefik
pytest tests/ -v

# Run a specific test module
pytest tests/test_service_discovery.py -v
```

## Content Index

| File | Description |
|---|---|
| `__init__.py` | Python package marker |
| `conftest.py` | Shared fixtures (Redis mocks, test configuration) |
| `test_heartbeat.py` | Tests for heartbeat registration (service name, error handling) |
| `test_service_discovery.py` | Tests for SCAN-based discovery, config generation, and atomic writes |
