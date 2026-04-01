# Shared Types

Core TypeScript type definitions and interfaces shared across the ScareVerseLab platform.

## Purpose

This directory defines the foundational abstractions for the ScareVerse cell and book architecture. All cell type implementations and book type implementations must conform to the interfaces defined here.

## Index

### Files

| File | Description |
|------|-------------|
| `BaseCell.ts` | `BaseCell` interface — defines the execution lifecycle, validation, and health-checking contract that every cell type must implement |
| `BaseBook.ts` | `BaseBook` interface — defines the DAG-based orchestration contract for composing multiple cells into a workflow |
| `BaseBookImpl.ts` | Abstract class implementing `BaseBook` — handles DAG validation, topological sorting, cell lifecycle management, and state transfer between cells |

## Key Abstractions

### `BaseCell`

The foundational execution interface for all cell types. Provides:

- **Execution lifecycle**: `initialize()`, `execute()`, `finalize()`, `abort()`
- **Validation**: `validate()` to check inputs before execution
- **Health checking**: `healthCheck()` to report readiness
- **Headless execution**: cells can run without a UI (useful for automated pipelines)

```ts
import type { BaseCell } from '@artifacts/shared/types/BaseCell'

class MyCell implements BaseCell {
  async execute(input: unknown): Promise<unknown> { /* ... */ }
  async validate(): Promise<boolean> { /* ... */ }
}
```

### `BaseBook`

The orchestration interface for composing cells into DAG (Directed Acyclic Graph) workflows. Enables:

- Reusable cell composition
- Declarative workflow definition
- Automatic state transfer between cells

### `BaseBookImpl`

Abstract class that provides the full DAG executor. Subclasses only need to implement `getDAG()` and `describe()`.

```ts
import { BaseBookImpl } from '@artifacts/shared/types/BaseBookImpl'

class MyBook extends BaseBookImpl {
  getDAG() {
    return {
      nodes: [/* cell instances */],
      edges: [/* dependencies */],
    }
  }
  describe() { return 'My custom workflow book' }
}
```

## Related Documentation

- [Shared Artifacts Root](../) - Overview of all shared artifacts
- [Shared Composables](../composables/) - `useBaseCellFeatures`, `useCellFactory` and others that implement these interfaces
- [Architecture](../../../docs/architecture/) - Cell and Book architecture overview
- [Adding New Cell Type](../../../docs/official/ADDING_NEW_CELL_TYPE.md) - Guide for implementing `BaseCell`
