# AssetPrototypingCell Tests

## Overview

This directory contains unit tests for the AssetPrototypingCell, which demonstrates cell composition patterns in the BaseCell v1.0 framework.

## Test Coverage

### Files
- **AssetPrototypingCell.test.ts**: Unit tests for AssetPrototypingCell (16 test cases)

### Coverage Areas

#### 1. Instantiation Tests
- Cell creation with sub-cells
- Property existence verification

#### 2. Metadata Tests (describe())
- Metadata structure validation
- Input/output schema verification
- Composition metadata (composedCells array)

#### 3. Validation Tests (validate())
- Valid input acceptance
- Required field validation (prompt)
- Empty/whitespace prompt rejection
- Prompt length validation (max 1000 chars)
- Optional field validation
- Generation mode validation
- Reconstruction params validation

#### 4. Execution Tests (execute())
- Complete pipeline execution
- Sub-cell parameter passing
- Data flow between cells (PNG → Mesh)
- Early validation failure
- PNG generation failure handling
- Mesh generation failure (partial success)
- Execution metadata tracking

#### 5. Lifecycle Tests
- setup(): Coordinated setup of all sub-cells
- teardown(): Coordinated teardown of all sub-cells
- Setup idempotency (no double setup)
- Teardown without setup

#### 6. Health Check Tests
- Healthy when all sub-cells healthy
- Unavailable when PNG cell unavailable
- Unavailable when Mesh cell unavailable
- Degraded when one sub-cell degraded
- Health check aggregation logic

#### 7. Composition Patterns
- Sequential execution verification
- Data flow demonstration

## Running Tests

### Run all tests
```bash
cd cockpit-vue
npm test AssetPrototypingCell.test.ts
```

### Run with coverage
```bash
npm run test:coverage -- AssetPrototypingCell.test.ts
```

### Run in watch mode
```bash
npm test -- --watch AssetPrototypingCell.test.ts
```

## Test Strategy

### Mocking
All sub-cells (PngGeneratorCell, MeshPrototypingCell) are mocked using Vitest mocks. This ensures:
- Fast test execution
- Isolated testing of composition logic
- Predictable test behavior

### Test Structure
Tests follow the AAA pattern:
- **Arrange**: Setup cell and mocks
- **Act**: Execute the method under test
- **Assert**: Verify expected behavior

## Expected Results

All 16 tests should pass:
- ✅ 1 instantiation test
- ✅ 3 describe() tests
- ✅ 8 validate() tests
- ✅ 7 execute() tests
- ✅ 2 setup() tests
- ✅ 2 teardown() tests
- ✅ 4 health_check() tests
- ✅ 2 composition pattern tests

## Integration with CI/CD

These tests are automatically run by the CI/CD pipeline on:
- Pull requests to `main` branch
- Commits to feature branches
- Nightly builds

## References

- **Implementation**: [AssetPrototypingCell.ts](../AssetPrototypingCell.ts)
- **Composition Guide**: [COMPOSITION_STRATEGY.md](../../../../../docs/issues/base-cell-v1-implementation/COMPOSITION_STRATEGY.md)
- **BaseCell Spec**: [TO_BE_SPECIFICATION.md](../../../../../docs/issues/base-cell-v1-implementation/TO_BE_SPECIFICATION.md)
