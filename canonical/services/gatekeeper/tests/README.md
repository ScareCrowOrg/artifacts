# GateKeeper Tests

Unit and integration tests for the GateKeeper service, covering job dispatch, routing, worker discovery, orchestration, and end-to-end pipeline behavior.

## Purpose

This directory contains the complete test suite for the GateKeeper service. Tests validate:
- Configuration loading and resolution
- Job routing by execution model (service vs subprocess)
- Worker discovery and availability detection
- Resource orchestration and scaling logic
- Virtual environment management
- Error handling and recovery
- Full end-to-end pipeline integration

## Directory Structure

```
tests/
├── __init__.py                    - Package marker
├── conftest.py                    - Shared fixtures (Redis mocks, job payloads)
├── test_config_loading.py         - Config resolution (Redis L1 → env fallback)
├── test_routing.py                - Job routing by execution model
├── test_orchestrator.py           - Resource orchestration decisions
├── test_metrics.py                - Metrics collection and reporting
├── test_gatekeeper_pooling.py     - Multi-source queue pooling strategy
├── test_worker_discovery.py       - Worker registry discovery from Redis
├── test_worker_availability.py    - Worker liveness and availability checks
├── test_venv_management.py        - Venv creation and isolation
├── test_venv_manager.py           - VenvManager class unit tests
├── test_error_handling.py         - Error paths and recovery behavior
├── test_integration_e2e.py        - End-to-end integration tests
├── test_integration_rembg.py      - Rembg worker integration tests
├── test_e2e_full_pipeline.py      - Full pipeline execution tests
└── test_phase3_integration.py     - Phase 3 feature integration tests
```

## How to Use

```bash
# Run all tests from the gatekeeper root
cd artifacts/canonical/services/gatekeeper
pip install -r requirements.txt
pytest tests/ -v

# Run a specific test module
pytest tests/test_routing.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

## Content Index

| File | Description |
|---|---|
| `__init__.py` | Python package marker |
| `conftest.py` | Shared pytest fixtures and Redis mock setup |
| `test_config_loading.py` | Tests for config resolution and fallback logic |
| `test_routing.py` | Tests for job routing by execution model |
| `test_orchestrator.py` | Tests for scale-up/down orchestration decisions |
| `test_metrics.py` | Tests for metrics collection |
| `test_gatekeeper_pooling.py` | Tests for queue pooling strategy |
| `test_worker_discovery.py` | Tests for worker registry discovery |
| `test_worker_availability.py` | Tests for worker liveness checks |
| `test_venv_management.py` | Tests for virtual environment lifecycle |
| `test_venv_manager.py` | Unit tests for VenvManager class |
| `test_error_handling.py` | Tests for error handling and recovery |
| `test_integration_e2e.py` | End-to-end integration tests |
| `test_integration_rembg.py` | Rembg worker integration tests |
| `test_e2e_full_pipeline.py` | Full pipeline execution tests |
| `test_phase3_integration.py` | Phase 3 integration tests |
