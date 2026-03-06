---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/backend/testing/test-remediation-2026-q1.md
themes:
  - cells
  - frontend
  - testing
modules:
  - frontend
code_verified: true
dead_docs_found: false
---
# 3D Mesh Prototyping Cell - Backend Tests

This directory contains tests for the 3D Mesh Prototyping Cell backend implementation.

## Test Files

### test_main.py
Tests for the legacy `execute_cell()` function and basic 3D mesh generation functionality.

### test_path_normalization.py
Tests for path normalization and handling in the 3D mesh generation pipeline.

### test_stable_fast_3d_client.py
Tests for the Stable Fast 3D API client integration.

### test_mesh_prototyping_cell_basecell.py
Comprehensive tests for the BaseCell v1.0 implementation of MeshPrototypingCell.

**Coverage**: >90% of MeshPrototypingCell class

**Key Test Areas**:
- ✅ BaseCell methods: execute(), describe(), validate(), health_check(), setup(), teardown()
- ✅ Generation modes: 'cloud-api', 'local-gpu' (default), 'manual-upload'
- ✅ External services: Redis job queue, Stable Fast 3D API (mocked)
- ✅ Parameter handling: Reconstruction params for all modes
- ✅ Validation: Missing inputImage, invalid modes
- ✅ Error handling: Queue failures, API errors, import errors
- ✅ Backward compatibility: execute_cell() wrapper

**Test Classes**:
- `TestMeshPrototypingCellBaseMethods` - BaseCell method implementations
- `TestMeshPrototypingCellExecute` - Execute method with different modes
- `TestGenerationModeRouting` - Routing logic for all modes
- `TestLocalGpuGeneration` - Redis job queueing and parameter passing
- `TestCloudApiGeneration` - Stable Fast 3D API integration
- `TestManualUpload` - Manual file upload handling
- `TestLegacyFunctions` - Mock mesh generation functions
- `TestBackwardCompatibility` - Legacy function wrappers
- `TestGlobalInstance` - Singleton instance management
- `TestErrorHandling` - Exception handling and edge cases
- `TestEndToEndScenarios` - Full workflows

**Total Tests**: 45+

## Running Tests

### Run All Tests
```bash
pytest artifacts/canonical/cell_types/3d-mesh-prototyping-cell/backend/tests/ -v
```

### Run Specific Test File
```bash
pytest artifacts/canonical/cell_types/3d-mesh-prototyping-cell/backend/tests/test_mesh_prototyping_cell_basecell.py -v
```

### Run with Coverage
```bash
pytest artifacts/canonical/cell_types/3d-mesh-prototyping-cell/backend/tests/ --cov=artifacts/canonical/cell_types/3d-mesh-prototyping-cell/backend/scripts --cov-report=term-missing
```

## Test Architecture

All external dependencies are mocked to ensure:
- **Fast execution** (<5 seconds total)
- **Deterministic results** (no flaky tests)
- **No external service dependencies** (Redis, GPU workers, APIs)

**Mocked Services**:
- Redis client (AsyncMock)
- Stable Fast 3D API (MagicMock)
- Job queue functions (AsyncMock)

## References

- **Implementation**: `../scripts/main.py`
- **BaseCell ABC**: `/backend/app/core/base_cell.py`
- **Testing Architecture**: `/docs/ARQUITETURA_TESTES.md`
