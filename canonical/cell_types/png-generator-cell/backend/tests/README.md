---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/frontend/architecture/dynamic-cell-loading-vite.md
themes:
  - cells
  - frontend
  - artifacts
modules:
  - frontend
code_verified: true
dead_docs_found: false
---
# PNG Generator Cell - Backend Tests

This directory contains tests for the PNG Generator Cell backend implementation.

## Test Files

### test_main.py
Tests for the legacy `execute_cell()` function and basic PNG generation functionality.

**Coverage Areas**:
- execute_cell() function with existing PNG
- execute_cell() with empty prompt
- Basic PNG generation workflow
- Error handling

### test_png_generator_cell_basecell.py
Comprehensive tests for the BaseCell v1.0 implementation of PngGeneratorCell.

**Coverage**: >90% of PngGeneratorCell class

**Key Test Areas**:
- ✅ BaseCell methods: execute(), describe(), validate(), health_check(), setup(), teardown()
- ✅ Action routing: 'generate' and 'removeBackground'
- ✅ External services: Stable Diffusion, Rembg/GPU Worker, Ollama (mocked)
- ✅ 3D asset mode: Prompt enhancement with Ollama orchestration
- ✅ Validation: Missing prompts, invalid actions, missing PNG for background removal
- ✅ Error handling: Service failures, import errors, unexpected exceptions
- ✅ Fallback mechanisms: When services unavailable
- ✅ Backward compatibility: execute_cell() wrapper

**Test Classes**:
- `TestPngGeneratorCellBaseMethods` - BaseCell method implementations
- `TestPngGeneratorCellExecute` - Execute method with different actions
- `TestGeneratePngAction` - PNG generation logic and Ollama integration
- `TestRemoveBackgroundAction` - Background removal via GPU Worker
- `TestBackwardCompatibility` - Legacy function wrappers
- `TestGlobalInstance` - Singleton instance management
- `TestErrorHandling` - Exception handling and edge cases
- `TestEndToEndScenarios` - Full workflows

**Total Tests**: 40+

## Running Tests

### Run All Tests
```bash
pytest artifacts/canonical/cell_types/png-generator-cell/backend/tests/ -v
```

### Run Specific Test File
```bash
pytest artifacts/canonical/cell_types/png-generator-cell/backend/tests/test_png_generator_cell_basecell.py -v
```

### Run with Coverage
```bash
pytest artifacts/canonical/cell_types/png-generator-cell/backend/tests/ --cov=artifacts/canonical/cell_types/png-generator-cell/backend/scripts --cov-report=term-missing
```

## Test Architecture

All external dependencies are mocked to ensure:
- **Fast execution** (<5 seconds total)
- **Deterministic results** (no flaky tests)
- **No external service dependencies** (Redis, GPU workers, APIs)

**Mocked Services**:
- Redis client (AsyncMock)
- Stable Diffusion service (AsyncMock)
- Rembg/GPU Worker (AsyncMock)
- Ollama service (AsyncMock)

## References

- **Implementation**: `../scripts/main.py`
- **BaseCell ABC**: `/backend/app/core/base_cell.py`
- **Testing Architecture**: `/docs/ARQUITETURA_TESTES.md`
