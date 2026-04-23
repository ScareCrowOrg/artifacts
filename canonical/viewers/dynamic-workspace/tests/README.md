# DynamicWorkspace Tests

Unit tests for the DynamicWorkspace v2 viewer composables, covering grid layout management, auto-save behavior, persistence, and container logic.

## Purpose

This directory validates the core composables of the DynamicWorkspace viewer using Vitest:
- **Grid layout tests**: Validates cell CRUD operations, position management, minimize/maximize toggles, and layout sync
- **Auto-save tests**: Uses fake timers to test debounce and interval logic synchronously
- **Persistence tests**: Validates load/save of workspace layouts via mocked API
- **Container logic tests**: Validates grid container rendering and interaction logic

## Directory Structure

```
tests/
├── useAutoSave.test.ts           - Tests for debounced + interval auto-save composable
├── useGridLayout.test.ts         - Tests for GridCell CRUD, position, and state toggles
├── usePersistenceManager.test.ts - Tests for layout load/save via CentralHub API
└── gridContainerLogic.test.ts    - Tests for grid container rendering logic
```

## How to Use

```bash
# Run from the dynamic-workspace root
cd artifacts/canonical/viewers/dynamic-workspace
npm test

# Run with coverage
npm run test:coverage
```

## Content Index

| File | Description |
|---|---|
| `useAutoSave.test.ts` | Tests for auto-save debounce and interval logic (fake timers) |
| `useGridLayout.test.ts` | Tests for addCell, removeCell, updateCell, toggleMinimize, syncLayoutPositions |
| `usePersistenceManager.test.ts` | Tests for layout load/save via mocked CentralHub API |
| `gridContainerLogic.test.ts` | Tests for grid container rendering and interaction |
