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
# Fragment Editor Cell - Tests

## Overview

This directory contains tests for the Fragment Editor Cell implementation.

## Test Files

- **FragmentEditorCell.test.ts**: Unit tests for the FragmentEditorCell class
  - Tests BaseCell interface implementation
  - Tests validation logic
  - Tests execute() method for all actions (create, edit, load)
  - Tests error handling

## Running Tests

```bash
# Run all tests
npm run test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage
```

## Test Coverage

Target coverage: **90%+**

Coverage areas:
- ✅ BaseCell interface methods (execute, describe, validate)
- ✅ Create fragment functionality
- ✅ Edit fragment functionality
- ✅ Load fragment functionality
- ✅ Input validation
- ✅ Error handling
- ✅ API integration (mocked)

## Test Structure

Tests follow the AAA pattern:
- **Arrange**: Set up test data and mocks
- **Act**: Execute the function under test
- **Assert**: Verify expected outcomes

## Mocking

The tests use Vitest for mocking:
- `apiFetch` service is mocked to simulate API responses
- No actual API calls are made during tests

## Adding New Tests

When adding new features to FragmentEditorCell:

1. Add corresponding test cases in `FragmentEditorCell.test.ts`
2. Ensure coverage stays above 90%
3. Test both success and error paths
4. Mock external dependencies appropriately

## Related Documentation

- [Fragment Editor Cell README](../../README.md)
- [BaseCell Interface](../../../../../cockpit-vue/src/types/BaseCell.ts)
- [Testing Architecture](../../../../../docs/official/ARQUITETURA_TESTES.md)
