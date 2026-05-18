---
processed: true
processed_date: 2026-02-06
themes:
  - official
  - documentation
  - orchestration
modules:
  - documentation
  - architecture
code_verified: true
---

# Adding New Book Types Guide

⚠️ **CRITICAL: BaseBook Interface is MANDATORY for Complex Workflows**
---

**Every orchestrator book MUST implement the `BaseBook` interface (via `AbstractBaseBook`).**
- `getDAG()` - **REQUIRED**
- `describe()` - **REQUIRED**
- `execute()`, `setup()`, `teardown()`, `health_check()` - Provided by AbstractBaseBook

Books that do not implement BaseBook violate the headless-first architecture and will be rejected in code review.

For simple utility operations between cells, use direct cell-to-cell calls. For orchestration, use BaseBook.

See: [BaseBook and BaseBook Implementation (Mandatory)](#basebook-and-basebook-implementation) section below.

---

## Overview

Books are **recommended orchestrators** that compose multiple cells into workflows via DAG-based coordination. Unlike cells (which typically handle atomic operations), books provide explicit state transfer and dependency management between cells.

### What is a Book?

A **Book** MUST implement the `BaseBook` interface (via extending `AbstractBaseBook`) and:
- ✅ Composes multiple **cells** into workflows (recommended pattern)
- ✅ Defines execution order via **DAG** (Directed Acyclic Graph)
- ✅ Automatically transfers state between cells
- ✅ Separates orchestration concerns from individual cell logic
- ❌ Should NOT contain business logic (delegate to cells)
- ❌ Should NOT contain other books (compose cells directly, not nested books)

### When to Use Cells vs Books (Pattern Recommendation)

| Concern | Cell | Book |
|---------|------|------|
| **Purpose** | Business logic / Atomic operations | Orchestration / Coordination |
| **Responsibility** | Domain logic, data processing | Workflow choreography, state transfer |
| **Composition** | Can call other cells if needed | Composes cells via DAG |
| **Example** | Generate image, process data, transform input | Sequence: Generate + enhance image + save |
| **See** | [ADDING_NEW_CELL_TYPE.md](./ADDING_NEW_CELL_TYPE.md) | This guide |

**Note**: While Books are the recommended pattern for orchestration, cells are flexible enough to call other cells directly when needed for utility operations. The key is choosing the right pattern for your use case.

### Real-World Examples

**Pattern A: Direct Cell-to-Cell Calls** (Utility/Helper Pattern)
```typescript
class ImageEnhancerCell implements BaseCell {
  private validator = new ImageValidatorCell()  // Utility call

  async execute(input) {
    const validated = await this.validator.execute(input)
    if (!validated.isValid) throw new Error('Invalid image')
    return this.enhance(validated.data)
  }
}
```

✅ Good for: Utility operations, validation helpers, reusable components
✅ Benefits: Simple, direct, minimal overhead

**Pattern B: Book-Based Orchestration** (Recommended for Complex Workflows)
```typescript
class AssetPrototypingBook extends AbstractBaseBook {
  getDAG() {
    return {
      nodes: [
        { id: 'png', cellType: 'png-generator-cell', input: (ctx) => ctx.bookInput },
        { id: 'mesh', cellType: 'mesh-generator-cell', input: (ctx) => ({ texture: ctx.outputs.png.result }) }
      ],
      edges: [{ from: 'png', to: 'mesh' }]
    }
  }
}
```

✅ Good for: Complex workflows, multi-step pipelines, dependency chains
✅ Benefits: Declarative, reusable cells, easy testing, parallelizable, observability

**Architecture Flexibility**: Choose the pattern that best fits your use case:
- Use **direct cell-to-cell calls** for simple utility operations
- Use **Books** for explicit orchestration of complex workflows
- Both patterns are valid; architecture is flexible enough to support both

## BaseBook and BaseBook Implementation (MANDATORY)

🚨 **All orchestrator books MUST implement BaseBook** (via extending `AbstractBaseBook`).

This is an architectural requirement for the headless-first system. There are NO exceptions for books that orchestrate multiple cells.

### BaseBook Interface (MANDATORY IMPLEMENTATION)

```typescript
interface BaseBook {
  // Execute the DAG workflow
  execute(input: Record<string, any>): Promise<BookResult>

  // Describe the book's capabilities
  describe(): Promise<CellMetadata>

  // Get the DAG definition (must be implemented by subclasses)
  getDAG(): DAGDefinition

  // Setup all cells
  setup(config: EnvironmentConfig): Promise<void>

  // Teardown all cells
  teardown(): Promise<void>

  // Check health of all cells
  health_check(): Promise<HealthCheckResult>
}
```

### AbstractBaseBook

You don't implement `BaseBook` directly. Instead, extend `AbstractBaseBook` which handles all the DAG execution logic:

```typescript
export abstract class AbstractBaseBook implements BaseBook {
  // You only implement these two:
  abstract getDAG(): DAGDefinition
  abstract describe(): Promise<CellMetadata>

  // Everything else is provided by AbstractBaseBook:
  // - DAG validation
  // - Topological sorting
  // - Cell lifecycle management
  // - State transfer
  // - Error handling
}
```

### Instance Composition Pattern (Optional)

**NEW**: BaseBook can optionally reference its Book runtime instance to access metadata when needed. This follows the PipelineItem → NotebookItem composition pattern.

```typescript
interface BaseBook {
  // Optional reference to the Book runtime instance
  book_instance?: {
    id: string
    assignee_id: string
    name: string
    description: string
    initial_data: Record<string, any>
    fragments: Array<string | Record<string, any>>
    refs: Record<string, string[]>
    cells: string[]
    children?: string[]
    created_at?: string
    updated_at?: string
  }
}
```

**Implementation Example:**

**TypeScript:**
```typescript
export class WorkflowBook extends AbstractBaseBook {
  book_instance?: Book  // Optional instance reference
  
  getDAG(): DAGDefinition {
    // Access metadata when available
    const config = this.book_instance?.initial_data || {}
    
    return {
      nodes: [
        { 
          id: 'validate', 
          cellType: 'validator-cell', 
          input: (ctx) => ctx.bookInput 
        },
        { 
          id: 'process', 
          cellType: 'processor-cell', 
          input: (ctx) => ({ 
            data: ctx.outputs.validate.validated,
            config: config  // Use book instance config
          })
        }
      ],
      edges: [{ from: 'validate', to: 'process' }]
    }
  }
  
  async describe(): Promise<CellMetadata> {
    return {
      id: 'workflow-book',
      name: 'Workflow Book',
      version: '1.0.0',
      description: 'Multi-step workflow',
      inputs: { data: { type: 'object', required: true } },
      outputs: { result: { type: 'object' } },
      tags: ['workflow', 'orchestration']
    }
  }
}
```

**Python:**
```python
from typing import Optional, Dict, Any
from app.core.base_book import BaseBook, DAGDefinition, DAGNode, DAGEdge, BookResult
from app.models.content import Book

class WorkflowBook(BaseBook):
    def __init__(self, book_instance: Optional[Book] = None):
        super().__init__(book_instance)
        # self.book_instance is now available
    
    def get_dag(self) -> DAGDefinition:
        # Access metadata when available
        config = self.book_instance.initial_data if self.book_instance else {}
        
        return DAGDefinition(
            nodes=[
                DAGNode(
                    id='validate',
                    cell_type='validator-cell',
                    input={'data': '{{bookInput.data}}'}
                ),
                DAGNode(
                    id='process',
                    cell_type='processor-cell',
                    input={'data': '{{outputs.validate.validated}}', 'config': config}
                )
            ],
            edges=[
                DAGEdge(from_node='validate', to_node='process')
            ]
        )
```

**Benefits:**
- ✅ Access to owner/assignee information (`assignee_id`)
- ✅ Access to initial configuration (`initial_data`)
- ✅ Access to execution history (`fragments`)
- ✅ Access to book structure (`cells`, `children`)
- ✅ Backward compatible (optional field)

### Key Concepts

**DAGDefinition** - Your workflow structure:
```typescript
{
  nodes: DAGNode[]  // Each node is a cell execution
  edges: DAGEdge[]  // Dependencies between nodes
}
```

**DAGNode** - A cell execution step:
```typescript
{
  id: string                          // 'step1'
  cellType: string                    // 'calculator-cell'
  input: Record<string, any> |        // Static input
         (context) => Record<string, any>  // Or dynamic
  label?: string                      // 'Calculate result'
  optional?: boolean                  // Can fail without failing book
}
```

**DAGEdge** - Dependency between nodes:
```typescript
{
  from: string      // 'step1'
  to: string        // 'step2'
  field?: string    // Output field to pass
  targetField?: string // Target field name
}
```

**ExecutionContext** - Available in node input:
```typescript
{
  outputs: Record<string, any>  // From previous nodes
  bookInput: Record<string, any> // Book's input
  metadata: {
    startTime: number
    currentNode?: string
    completedNodes: string[]
    failedNodes: string[]
  }
}
```

**BookResult** - What `execute()` returns:
```typescript
{
  success: boolean
  output: Record<string, any>        // Aggregated results
  nodeResults?: Record<string, CellResult>  // Individual node results
  execution_time: number
  executionTrace?: Array<{            // Debugging
    nodeId: string
    startTime: number
    endTime: number
    success: boolean
    error?: string
  }>
}
```

## 🚨 MANDATORY REQUIREMENTS CHECKLIST

Before starting any book implementation, your book MUST satisfy all of these:

- [ ] **Extends `AbstractBaseBook`** - Not just implementing BaseBook, must extend the abstract class
- [ ] **Implements `getDAG()`** - Returns a valid DAGDefinition with nodes and edges
- [ ] **Implements `describe()`** - Returns CellMetadata with id, name, version, inputs, outputs
- [ ] **Has valid DAG structure** - No cycles, proper node/edge definitions
- [ ] **Creates type.json** - Book type definition with symlink
- [ ] **TypeScript for implementation** - All book code uses TypeScript
- [ ] **Documentation included** - `docs/README.md` with workflow diagram and examples
- [ ] **Tests included** - 90%+ coverage for DAG execution and node sequencing

**If your book doesn't extend AbstractBaseBook, it will be rejected in code review. Period.**

**Note on Cell-to-Cell Calls**: If you only need simple utility operations (not orchestration), use direct cell-to-cell calls. Books are for explicit orchestration with DAG-based coordination.

---

## Quick Start

### 1. Create Directory Structure

```bash
mkdir -p artifacts/canonical/book_types/{book_id}/{frontend/tests,docs}
```

### 2. Create Notebook Item Type Definition

Create `artifacts/canonical/notebook_item_types/{book_id}.json`:

```json
{
  "id": "my-workflow-book",
  "name": "My Workflow Book",
  "description": "Orchestrates cells for a specific workflow",
  "category": "orchestrator",
  "version": "1.0.0",
  "can_render_dynamically": false,
  "default_refs": {
    "view": ["book_types/my-workflow-book/frontend/MyWorkflowBook.ts"],
    "docs": ["book_types/my-workflow-book/docs/README.md"]
  },
  "default_initial_data": {},
  "allow_instance_override_refs": false,
  "properties_schema": {}
}
```

### 3. Create Symlink

```bash
cd artifacts/canonical/book_types/{book_id}
ln -s ../../notebook_item_types/{book_id}.json type.json
```

### 4. Implement BaseBook Subclass

Create `artifacts/canonical/book_types/my-workflow-book/frontend/MyWorkflowBook.ts`:

```typescript
import { AbstractBaseBook } from '@/types/BaseBookImpl'
import type { DAGDefinition } from '@/types/BaseBook'
import type { CellMetadata } from '@/types/BaseCell'

export class MyWorkflowBook extends AbstractBaseBook {
  /**
   * Define your workflow as a DAG
   * Nodes = cells to execute
   * Edges = dependencies between cells
   */
  getDAG(): DAGDefinition {
    return {
      nodes: [
        // Step 1: Generate PNG from prompt
        {
          id: 'png_generation',
          cellType: 'png-generator-cell',
          label: 'Generate PNG from prompt',
          input: (ctx) => ({
            prompt: ctx.bookInput.prompt,
            width: 512,
            height: 512
          })
        },

        // Step 2: Enhance the PNG
        {
          id: 'image_enhancement',
          cellType: 'image-enhancer-cell',
          label: 'Enhance generated image',
          input: (ctx) => ({
            image_url: ctx.outputs.png_generation.image_url,
            style: ctx.bookInput.style || 'vivid'
          }),
          optional: false  // Book fails if this step fails
        },

        // Step 3: Generate 3D mesh from texture
        {
          id: 'mesh_generation',
          cellType: '3d-mesh-prototyping-cell',
          label: 'Generate 3D mesh',
          input: (ctx) => ({
            texture_url: ctx.outputs.image_enhancement.enhanced_image,
            model_type: ctx.bookInput.modelType || 'standard'
          })
        }
      ],

      // Define execution order
      edges: [
        { from: 'png_generation', to: 'image_enhancement' },
        { from: 'image_enhancement', to: 'mesh_generation' }
      ]
    }
  }

  /**
   * Describe what this book does
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'my-workflow-book',
      name: 'My Workflow Book',
      version: '1.0.0',
      description: 'Generates PNG, enhances it, then creates 3D mesh',

      inputs: {
        prompt: {
          type: 'string',
          description: 'Text prompt for image generation',
          required: true
        },
        style: {
          type: 'string',
          description: 'Enhancement style (vivid, subtle, etc)',
          required: false,
          default: 'vivid'
        },
        modelType: {
          type: 'string',
          description: '3D model type',
          required: false,
          default: 'standard'
        }
      },

      outputs: {
        image_url: {
          type: 'string',
          description: 'URL of enhanced PNG image'
        },
        mesh_url: {
          type: 'string',
          description: 'URL of generated 3D mesh (GLB format)'
        }
      },

      tags: ['image', 'book', 'orchestration', '3d', 'composition'],
      estimated_duration_seconds: 60
    }
  }
}
```

### 5. Register Cells in the Book

Create `artifacts/canonical/book_types/my-workflow-book/frontend/index.ts`:

```typescript
import { registerCellType } from '@/types/BaseBookImpl'
import { PngGeneratorCell } from '@/cells/png-generator-cell'
import { ImageEnhancerCell } from '@/cells/image-enhancer-cell'
import { MeshPrototypingCell } from '@/cells/mesh-prototyping-cell'

export function registerMyWorkflowCells(): void {
  registerCellType('png-generator-cell', () => new PngGeneratorCell())
  registerCellType('image-enhancer-cell', () => new ImageEnhancerCell())
  registerCellType('3d-mesh-prototyping-cell', () => new MeshPrototypingCell())
}

export { MyWorkflowBook } from './MyWorkflowBook'
```

### 6. Write Tests

Create `artifacts/canonical/book_types/my-workflow-book/frontend/tests/MyWorkflowBook.test.ts`:

```typescript
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { MyWorkflowBook } from '../MyWorkflowBook'
import { registerMyWorkflowCells } from '../index'

describe('MyWorkflowBook', () => {
  let book: MyWorkflowBook

  beforeAll(async () => {
    // Register all cells before creating book
    registerMyWorkflowCells()

    // Create and setup book
    book = new MyWorkflowBook()
    await book.setup({ headless_mode: true })
  })

  afterAll(async () => {
    await book.teardown()
  })

  it('should describe itself', async () => {
    const metadata = await book.describe()
    expect(metadata.id).toBe('my-workflow-book')
    expect(metadata.name).toBe('My Workflow Book')
    expect(metadata.inputs).toBeDefined()
    expect(metadata.outputs).toBeDefined()
  })

  it('should execute workflow successfully', async () => {
    const result = await book.execute({
      prompt: 'a fantasy sword',
      style: 'vivid',
      modelType: 'standard'
    })

    expect(result.success).toBe(true)
    expect(result.output).toBeDefined()
    expect(result.nodeResults).toBeDefined()
    expect(result.executionTrace).toBeDefined()
  })

  it('should trace execution of all nodes', async () => {
    const result = await book.execute({
      prompt: 'a fantasy sword'
    })

    expect(result.executionTrace?.length).toBeGreaterThan(0)
    const traceNodes = result.executionTrace?.map(t => t.nodeId) || []
    expect(traceNodes).toContain('png_generation')
    expect(traceNodes).toContain('image_enhancement')
    expect(traceNodes).toContain('mesh_generation')
  })

  it('should health check all cells', async () => {
    const health = await book.health_check()
    expect(health.status).toBe('healthy')
    expect(health.can_execute).toBe(true)
  })

  it('should fail gracefully on invalid input', async () => {
    const result = await book.execute({})  // Missing required prompt

    // Depends on implementation - some books may fail, others may continue
    // Adjust based on your error handling strategy
  })
})
```

### 7. Create Documentation

Create `artifacts/canonical/book_types/my-workflow-book/docs/README.md`:

```markdown
# My Workflow Book

## Overview

Orchestrates a complete image-to-3D workflow:
1. Generate PNG from text prompt
2. Enhance the generated image
3. Create 3D mesh from texture

## Input

- `prompt` (string, required): Text description of what to generate
- `style` (string, optional): Enhancement style - default "vivid"
- `modelType` (string, optional): 3D model type - default "standard"

## Output

- `image_url`: URL of the final enhanced PNG
- `mesh_url`: URL of generated 3D mesh (GLB format)

## Execution Flow

```
[Prompt] → PNG Generation → Image Enhancement → 3D Mesh Generation → [GLB + PNG]
```

## DAG Structure

```
png_generation (png-generator-cell)
    ↓
image_enhancement (image-enhancer-cell)
    ↓
mesh_generation (3d-mesh-prototyping-cell)
```

## Usage Example

```typescript
import { MyWorkflowBook } from './MyWorkflowBook'
import { registerMyWorkflowCells } from './index'

// Register cells
registerMyWorkflowCells()

// Create and execute
const book = new MyWorkflowBook()
await book.setup({ headless_mode: true })

const result = await book.execute({
  prompt: 'a detailed golden sword with glowing runes',
  style: 'vivid',
  modelType: 'high_detail'
})

console.log('Image:', result.output.image_url)
console.log('Mesh:', result.output.mesh_url)
console.log('Execution time:', result.execution_time, 'ms')
```

## Performance

- **Total Execution Time**: ~60 seconds average
- **PNG Generation**: ~15-20s
- **Image Enhancement**: ~10-15s
- **3D Mesh Generation**: ~30-40s

## Debugging

Check `executionTrace` to see timing of each node:

```typescript
const result = await book.execute(input)
result.executionTrace?.forEach(trace => {
  console.log(`${trace.nodeId}: ${trace.endTime - trace.startTime}ms`)
})
```

## Optional Nodes

Nodes with `optional: true` can fail without failing the entire book.
```

## Advanced Patterns

### Input Resolution

Nodes can reference previous outputs using template strings or functions:

**Template Strings**:
```typescript
{
  id: 'step2',
  cellType: 'processor',
  input: {
    data: '{{outputs.step1.result}}',        // From previous node
    userInput: '{{bookInput.param}}'         // From book input
  }
}
```

**Functions** (Recommended for complex logic):
```typescript
{
  id: 'step2',
  cellType: 'processor',
  input: (ctx) => {
    const step1Result = ctx.outputs.step1
    return {
      data: step1Result.result || 'default',
      userInput: ctx.bookInput.param,
      metadata: {
        previous: step1Result.metadata
      }
    }
  }
}
```

### Error Handling

**Optional Nodes** - Continue even if node fails:
```typescript
{
  id: 'optional_enhancement',
  cellType: 'enhancer',
  optional: true,  // Book continues if this fails
  input: (ctx) => ({ image: ctx.outputs.generation.image })
}
```

**Parallel Execution** (DAG supports it):
```typescript
{
  nodes: [
    {
      id: 'generate_v1',
      cellType: 'png-generator',
      input: (ctx) => ({ prompt: ctx.bookInput.prompt + ' style A' })
    },
    {
      id: 'generate_v2',
      cellType: 'png-generator',
      input: (ctx) => ({ prompt: ctx.bookInput.prompt + ' style B' })
    }
  ],
  edges: []  // No dependencies = can run in parallel
}
```

### Complex Workflows

For workflows with 5+ cells, consider breaking into multiple books:

```typescript
class PipelineBook extends AbstractBaseBook {
  getDAG() {
    return {
      nodes: [
        {
          id: 'stage1',
          cellType: 'stage1-book',  // Compose book as node (future)
          input: (ctx) => ctx.bookInput
        },
        {
          id: 'stage2',
          cellType: 'stage2-book',
          input: (ctx) => ({ data: ctx.outputs.stage1.output })
        }
      ],
      edges: [{ from: 'stage1', to: 'stage2' }]
    }
  }
}
```

## Directory Structure Reference

```
my-workflow-book/
├── type.json                    # REQUIRED: Symlink to notebook_item_types
├── frontend/                    # REQUIRED: Implementation
│   ├── MyWorkflowBook.ts        # Main class extending AbstractBaseBook
│   ├── index.ts                 # Cell registration
│   └── tests/
│       ├── MyWorkflowBook.test.ts
│       └── README.md
└── docs/
    └── README.md                # REQUIRED: Documentation
```

## Best Practices

### 0. Vue 3 Reactivity Isolation (If Book Has Frontend UI)

⚠️ **If your book includes a frontend View component, follow Buffer Local Pattern**

Books that render UI components must apply the same **Reactivity Isolation** principles as cells:

- Use flat `ref` variables for user interactions (not cascading computeds)
- Read from `props.book` only on initialization
- Sync changes back to book instance only on explicit actions

See: [`REACTIVITY_ISOLATION.md`](./REACTIVITY_ISOLATION.md) for complete patterns and checklist.

---

### 1. Keep DAGs Simple (2-5 nodes)

Complex workflows should be broken into multiple books.

```typescript
// ✅ Good
getDAG() {
  return {
    nodes: [
      { id: 'prep', cellType: 'prep', input: ... },
      { id: 'process', cellType: 'process', input: ... },
      { id: 'finalize', cellType: 'finalize', input: ... }
    ],
    edges: [
      { from: 'prep', to: 'process' },
      { from: 'process', to: 'finalize' }
    ]
  }
}

// ❌ Bad - 10 nodes, hard to understand
getDAG() {
  return {
    nodes: [node1, node2, node3, ..., node10],
    edges: [...]
  }
}
```

### 2. Use Functions for Dynamic Input

Functions are clearer and more maintainable than template strings:

```typescript
// ✅ Good
input: (ctx) => ({
  texture: ctx.outputs.png_gen.image_url,
  quality: ctx.bookInput.quality || 'high'
})

// ❌ Acceptable but less readable
input: {
  texture: '{{outputs.png_gen.image_url}}',
  quality: '{{bookInput.quality}}'
}
```

### 3. Validate Composed Cells

Register cells with type checking:

```typescript
// ✅ Type-safe registration
registerCellType('calculator', () => {
  const cell = new CalculatorCell()
  // Could add type validation here
  return cell as BaseCell
})
```

### 4. Document DAG Flow

Use labels and comments:

```typescript
{
  id: 'analysis',
  cellType: 'analyzer',
  label: 'Analyze image content and extract features',  // Clear purpose
  input: (ctx) => ({ image: ctx.outputs.prep.image })
}
```

### 5. Test All Scenarios

Include tests for:
- Happy path (all nodes succeed)
- Optional node failures
- Invalid input
- Health checks
- Execution trace correctness

## Common Issues

### ⛔ Book Does Not Extend AbstractBaseBook (WILL BE REJECTED)

**This is the #1 reason books are rejected in code review.**

**Symptom**: Your book has `getDAG()` but doesn't extend `AbstractBaseBook`.

**Fix**:
1. Extend `AbstractBaseBook` (not just implementing `BaseBook`)
2. Implement the two required abstract methods: `getDAG()` and `describe()`
3. Let AbstractBaseBook provide all lifecycle management

**Example - WRONG ❌**:
```typescript
export class MyBook implements BaseBook {
  // Manual implementation of every method ❌
  async execute(input) { ... }
  async setup(config) { ... }
  async teardown() { ... }
  // ❌ Too much code, should use AbstractBaseBook
}
```

**Example - RIGHT ✅**:
```typescript
export class MyBook extends AbstractBaseBook {
  // Only implement these two - everything else is provided
  getDAG(): DAGDefinition {
    return { nodes: [...], edges: [...] }
  }

  async describe(): Promise<CellMetadata> {
    return { id: 'my-book', name: 'My Book', ... }
  }
}
```

**Why?** AbstractBaseBook handles:
- DAG validation and cycle detection
- Topological sorting and execution order
- Cell lifecycle management (setup/teardown)
- Error handling and recovery
- Execution tracing

**No exceptions. All orchestrator books must extend AbstractBaseBook.**

---

### Cell Type Not Registered

```
Error: Cell type not registered: calculator-cell
```

**Solution**: Call `registerMyWorkflowCells()` before creating book instance.

```typescript
registerMyWorkflowCells()  // Must happen first
const book = new MyWorkflowBook()
```

### DAG Contains Cycle

```
Error: DAG contains a cycle - must be acyclic
```

**Solution**: Check edges don't create circular dependencies.

```
A → B → C → A  // ❌ Cycle
A → B → C      // ✅ Acyclic
```

### Input Mapping Not Working

```
// Result shows undefined outputs
console.log(ctx.outputs.png_gen.image_url)  // undefined
```

**Check**:
1. Node ID matches exactly: `png_gen` not `png_generation`
2. Output field exists in cell result
3. Edge connects nodes in correct direction

### Book Execution Too Slow

- Check `executionTrace` to identify slow nodes
- Consider parallel nodes (no dependencies between them)
- Profile individual cells in isolation

## Resources

**Type Definitions**:
- [BaseBook.ts](../../artifacts/shared/types/BaseBook.ts) - Interface and utilities
- [BaseBookImpl.ts](../../artifacts/shared/types/BaseBookImpl.ts) - Abstract implementation
- [BaseCell.ts](../../artifacts/shared/types/BaseCell.ts) - Cell interface for composition

**Examples**:
- [asset-prototyping-book](../../artifacts/canonical/book_types/asset-prototyping-book/) - Reference implementation
- Tests in `frontend/tests/`

**Related Guides**:
- [ADDING_NEW_CELL_TYPE.md](./ADDING_NEW_CELL_TYPE.md) - How to create cells to compose
- [artifacts/README.md](../../artifacts/README.md) - Artifact architecture overview

---

## 🚨 FINAL REMINDER: AbstractBaseBook is NOT Optional

If you're creating an orchestrator book, here's the ONE THING you need to remember:

**Your book MUST extend `AbstractBaseBook`.**

Not "should". Not "preferably". **MUST.**

- If you skip this, your PR will be rejected.
- If you extend it, your book will work with the headless-first architecture.
- If you have questions, refer to the [BaseBook and BaseBook Implementation (MANDATORY)](#basebook-and-basebook-implementation) section.

This is the architectural requirement that enables:
- ✅ Consistent DAG-based orchestration
- ✅ Proper cell composition and lifecycle
- ✅ Headless execution (scripts, automation, agents)
- ✅ Future extensibility and parallelization

**For simple utility operations**, use direct cell-to-cell calls. But for actual orchestration with explicit workflows, you must use AbstractBaseBook.

---

**Last Updated**: 2026-02-06
**Version**: 1.0.1 - Added explicit BaseBook mandatory requirements
