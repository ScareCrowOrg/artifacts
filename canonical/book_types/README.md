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
# Book Types - Canonical Books

This directory contains canonical "Book" implementations in the ScareVerse system. Books are DAG-based orchestrators that compose multiple cells into reusable workflows.

## Overview

Books solve the problem of orchestration complexity by separating concerns:
- **Cells** are atomic executors (do one thing well)
- **Books** are orchestrators (coordinate multiple cells via DAG)

### Key Benefits

1. **Declarative Workflows**: Define execution as DAG (nodes + edges)
2. **Automatic State Transfer**: No manual passing of data between cells
3. **Reusable Cells**: Same cells can be used in different books
4. **Testable**: Orchestration logic can be tested independently
5. **No Code Duplication**: Common patterns defined once

## Structure

Each book type follows this structure:

```
book-name/
├── frontend/
│   ├── BookName.ts          # Book implementation
│   └── tests/
│       ├── BookName.test.ts # Unit tests
│       └── README.md        # Test documentation
└── type.json               # Book metadata (optional)
```

## Available Books

### Asset Prototyping Book

**Location**: `asset-prototyping-book/`

**Purpose**: Creates complete 3D assets from text prompts by orchestrating PNG generation and 3D mesh creation.

**DAG Flow**:
```
prompt → [PngGeneratorCell] → texture_png → [MeshPrototypingCell] → mesh_glb
```

**Usage**:
```typescript
import { AssetPrototypingBook, registerAssetPrototypingCells } from '@/artifacts/canonical/book_types/asset-prototyping-book/frontend/AssetPrototypingBook'

// Register cells once
registerAssetPrototypingCells()

// Create and use book
const book = new AssetPrototypingBook()
await book.setup({ headless_mode: true })

const result = await book.execute({
  prompt: 'a fantasy sword',
  asset3dMode: true,
  generationMode: 'cloud-api'
})

console.log(result.output.texturePng)
console.log(result.output.meshGlbUrl)

await book.teardown()
```

## Creating New Books

### 1. Define Your Workflow

Identify the cells you need and their dependencies:
- What cells will you use?
- What's the execution order?
- How does data flow between cells?

### 2. Extend AbstractBaseBook

```typescript
import { AbstractBaseBook } from '@/types/BaseBookImpl'
import type { DAGDefinition } from '@/types/BaseBook'
import type { CellMetadata } from '@/types/BaseCell'

export class MyWorkflowBook extends AbstractBaseBook {
  getDAG(): DAGDefinition {
    return {
      nodes: [
        {
          id: 'step1',
          cellType: 'cell-type-1',
          input: (ctx) => ({ param: ctx.bookInput.value })
        },
        {
          id: 'step2',
          cellType: 'cell-type-2',
          input: (ctx) => ({ data: ctx.outputs.step1.result })
        }
      ],
      edges: [
        { from: 'step1', to: 'step2' }
      ]
    }
  }
  
  async describe(): Promise<CellMetadata> {
    return {
      id: 'my-workflow-book',
      name: 'My Workflow',
      version: '1.0.0',
      description: 'Does something useful',
      inputs: { /* ... */ },
      outputs: { /* ... */ },
      tags: ['workflow', 'book']
    }
  }
}
```

### 3. Register Cell Types

```typescript
import { registerCellType } from '@/types/BaseBookImpl'

export function registerMyWorkflowCells() {
  registerCellType('cell-type-1', () => new CellType1())
  registerCellType('cell-type-2', () => new CellType2())
}
```

### 4. Write Tests

```typescript
import { describe, it, expect, beforeAll, afterAll } from 'vitest'

describe('MyWorkflowBook', () => {
  let book: MyWorkflowBook
  
  beforeAll(async () => {
    registerMyWorkflowCells()
    book = new MyWorkflowBook()
    await book.setup({ headless_mode: true })
  })
  
  afterAll(async () => {
    await book.teardown()
  })
  
  it('should execute workflow successfully', async () => {
    const result = await book.execute({ value: 'test' })
    expect(result.success).toBe(true)
  })
})
```

## DAG Reference

### Node Definition

```typescript
{
  id: 'unique-node-id',          // Unique identifier
  cellType: 'registered-cell',   // Must be registered
  label: 'Human Label',          // Optional display name
  optional: false,               // Can fail without failing book
  input: {                       // Static input
    param: 'value'
  }
  // OR
  input: (context) => ({         // Dynamic input
    param: context.bookInput.value,
    data: context.outputs.prevNode.result
  })
}
```

### Edge Definition

```typescript
{
  from: 'source-node-id',        // Dependency
  to: 'target-node-id',          // Dependent
  field: 'output-field',         // Optional: specific field
  targetField: 'input-field'     // Optional: map to different name
}
```

### Input Resolution

Books support template strings and functions for input resolution:

**Template Strings**:
```typescript
{
  prompt: '{{bookInput.userPrompt}}',      // From book input
  image: '{{outputs.nodeId.fieldName}}'   // From previous node
}
```

**Functions** (recommended for complex logic):
```typescript
input: (context) => ({
  prompt: context.bookInput.prompt,
  enhanced: context.outputs.enhance?.result || 'default'
})
```

## Best Practices

### 1. Keep DAGs Simple

- Aim for 2-5 nodes per book
- For complex workflows, create multiple books
- Use clear, descriptive node IDs

### 2. Handle Errors Gracefully

- Use `optional: true` for non-critical nodes
- Provide meaningful error messages
- Test failure scenarios

### 3. Document Dependencies

- List required cell types in README
- Document expected input/output formats
- Provide usage examples

### 4. Test Thoroughly

- Test happy path
- Test error cases
- Test with different inputs
- Mock external dependencies

## Architecture

### BaseBook Interface

All books implement the `BaseBook` interface:

```typescript
interface BaseBook {
  execute(input: Record<string, any>): Promise<BookResult>
  describe(): Promise<CellMetadata>
  getDAG(): DAGDefinition
  setup(config: EnvironmentConfig): Promise<void>
  teardown(): Promise<void>
  health_check(): Promise<HealthCheckResult>
}
```

### Execution Flow

1. **Validation**: DAG structure validated (no cycles, valid nodes)
2. **Topological Sort**: Determine execution order
3. **Cell Instantiation**: Create cell instances from registry
4. **Setup**: Initialize all cells
5. **Execution**: Run nodes in order, transfer state
6. **Aggregation**: Combine results into output
7. **Teardown**: Cleanup all cells

## Related

- [BaseCell Framework](../../cell_types/README.md) - Atomic cell execution
- [BaseBook Types](../../../cockpit-vue/src/types/BaseBook.ts) - Type definitions
- [BaseBook Implementation](../../../cockpit-vue/src/types/BaseBookImpl.ts) - Abstract base class
- [Cell Types](../../cell_types/) - Available cells for composition

## Migration Guide

### From Cell-Based Orchestration

If you have a cell that contains other cells (like the old `AssetPrototypingCell`):

1. **Identify Sub-Cells**: List all cells being orchestrated
2. **Define DAG**: Map execution flow as nodes and edges
3. **Create Book**: Extend `AbstractBaseBook`
4. **Register Cells**: Use `registerCellType()`
5. **Test**: Ensure workflow produces same results
6. **Deprecate Old Cell**: Mark as deprecated, maintain for compatibility

### Example

**Before** (Cell-based):
```typescript
class OrchestrationCell implements BaseCell {
  private cell1 = new Cell1()
  private cell2 = new Cell2()
  
  async execute(input) {
    const result1 = await this.cell1.execute(input)
    const result2 = await this.cell2.execute({ data: result1.output })
    return { output: result2.output }
  }
}
```

**After** (Book-based):
```typescript
class OrchestrationBook extends AbstractBaseBook {
  getDAG() {
    return {
      nodes: [
        { id: 'step1', cellType: 'cell1', input: (ctx) => ctx.bookInput },
        { id: 'step2', cellType: 'cell2', input: (ctx) => ({ data: ctx.outputs.step1 }) }
      ],
      edges: [{ from: 'step1', to: 'step2' }]
    }
  }
}
```

## Notes

- Books should focus on orchestration, not business logic
- Keep cells atomic and reusable
- Use descriptive names for nodes and edges
- Document expected execution time
- Consider parallel execution where possible
