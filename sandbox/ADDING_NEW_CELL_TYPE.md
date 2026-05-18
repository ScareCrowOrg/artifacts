---
processed: true
processed_date: 2025-12-12
themes:
  - official
  - documentation
modules:
  - documentation
code_verified: true
dead_docs_found: false
---


# Adding New Cell Types Guide

⚠️ **CRITICAL: BaseCell Interface is MANDATORY**
---

**Every new cell MUST implement the `BaseCell` interface. This is not optional.**
- `execute(input)` - **REQUIRED**
- `describe()` - **REQUIRED**
- `validate(input)` - **REQUIRED**

Cells that do not implement BaseCell violate the headless-first architecture and will be rejected in code review.

See: [BaseCell Interface (Mandatory)](#basecel-interface-mandatory) section below.

---

## Overview

The plug-and-play cell architecture allows you to add new cell types without modifying core system code. Each cell type is self-contained in its own directory with all necessary components.

### What is a Cell?

A **Cell** is an executor that **MUST implement the `BaseCell` interface**:
- ✅ Implements the 3 required BaseCell methods: `execute()`, `describe()`, `validate()`
- ✅ Implements business logic or atomic operations
- ✅ Can execute locally (pure TypeScript) or via backend (Python)
- ✅ Can call other cells directly for utility operations (when needed)
- ✅ Can be composed into **Books** (orchestrators) for complex workflows
- ✅ Supports headless execution, validation, health checking

### When to Use Cells vs Books

| Concern | Cell | Book |
|---------|------|------|
| **Purpose** | Atomic execution | Orchestration |
| **Logic** | Business logic | Coordination |
| **Composition** | Doesn't contain cells | Composes cells |
| **Example** | Generate image, process data | Generate + enhance image |
| **See** | This guide | [ADDING_NEW_BOOK_TYPE.md](./ADDING_NEW_BOOK_TYPE.md) |

---

## 🚨 NO NEW ENDPOINTS - Use Existing Endpoints Only

⛔ **CRITICAL**: Cells MUST NOT create new API endpoints.

All cell execution must use **pre-existing endpoints** in `backend/app/routers/cells_router.py`.

### Available Endpoints (Use These)

| Endpoint | Purpose | When to Use |
|----------|---------|------------|
| `POST /api/cells/create` | Create a cell instance | User creates a cell in notebook |
| `POST /api/cells/{cell_id}/execute` | Execute a persisted cell | Cell was created & saved to DB |
| `POST /api/cells/execute-ephemeral` | Execute ephemeral cell (no DB) | Utility cells, one-off operations |

### ❌ DO NOT Create New Endpoints

**Wrong** ❌:
```python
# backend/app/routers/my_cell_router.py
@router.post("/my-cell/process")  # ❌ NEW ENDPOINT
async def my_cell_process(...):
    ...
```

**Correct** ✅:
```typescript
// frontend/MyCell.ts
import { apiFetch } from '@/services/apiService'

export class MyCell extends BaseCell {
  async execute(input: Record<string, any>): Promise<CellResult> {
    // Call existing endpoint - apiFetch handles auth automatically
    const response = await apiFetch('/api/cells/execute-ephemeral', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        cell_type: 'my-cell-type',
        input_data: input
      })
    })
    // apiFetch automatically:
    // - Adds Authorization header with Bearer token
    // - Detects 401 errors
    // - Attempts token refresh
    // - Retries with new token if refresh succeeds
    const result = await response.json()
    return result
  }
}
```

### How It Works

**For Regular Cells** (user creates instance):
1. User creates cell → `POST /api/cells/create`
2. Cell gets persisted with `cell_id` in DB
3. Cell execution → `POST /api/cells/{cell_id}/execute`
4. Endpoint dynamically loads `backend/scripts/main.py`
5. Calls `execute_cell(cell_data)` function

**For Ephemeral Cells** (utility, no DB):
1. Cell is never instantiated by user (marked `category: "ephemeral"` in type.json)
2. Other cells import and use programmatically
3. Cell execution → `POST /api/cells/execute-ephemeral` with `cell_type` and `input_data`
4. Endpoint dynamically loads `backend/scripts/main.py`
5. Calls `execute_cell(cell_data)` function

**Key Point**: The endpoint system dynamically loads your cell's backend script by cell type ID. No need for custom endpoints.

---

## BaseCell Interface (MANDATORY)

🚨 **All cells MUST implement the `BaseCell` interface** (from `artifacts/shared/types/BaseCell.ts`).

This is an architectural requirement for the headless-first system. There are NO exceptions.

### Core Methods (REQUIRED - No Exceptions)

```typescript
interface BaseCell {
  // Execute the cell's main logic
  execute(input: Record<string, any>): Promise<CellResult>

  // Describe the cell's capabilities
  describe(): Promise<CellMetadata>

  // Validate input before execution
  validate(input: Record<string, any>): ValidationError[]
}
```

### Optional Lifecycle Methods

```typescript
interface BaseCell {
  // Initialize resources (called once before first execute)
  setup?(config: EnvironmentConfig): Promise<void>

  // Release resources (called when cell is destroyed)
  teardown?(): Promise<void>

  // Check if cell can execute (for cells with external dependencies)
  health_check?(): Promise<HealthCheckResult>

  // Execute complete lifecycle atomically (setup → execute → save → show)
  run?(lifecycle: LifecycleConfig): Promise<CellResult>
}
```

### Instance Composition Pattern (Optional)

**NEW**: BaseCell can optionally reference its Cell runtime instance to access metadata when needed. This follows the PipelineItem → NotebookItem composition pattern.

```typescript
interface BaseCell {
  // Optional reference to the Cell runtime instance
  cell_instance?: {
    id: string
    assignee_id: string
    initial_data: Record<string, any>
    fragments: Array<string | Record<string, any>>
    refs: Record<string, string[]>
    version?: string
    created_at?: string
    updated_at?: string
  }
}
```

**Two Implementation Patterns:**

**Pattern A: Utility Cell (No Instance)**
```typescript
// Pure utility cell - no context needed
export class ValidatorCell extends BaseCell {
  // No cell_instance field needed

  async execute(input: Record<string, any>): Promise<CellResult> {
    const isValid = this.validateInput(input)
    return {
      success: isValid,
      output: { valid: isValid },
      execution_time: 5
    }
  }
  // ... other methods
}
```

**Pattern B: Context-Aware Cell (With Instance)**
```typescript
// Context-aware cell - accesses instance metadata
export class DataProcessingCell extends BaseCell {
  cell_instance?: Cell  // Optional instance reference

  async execute(input: Record<string, any>): Promise<CellResult> {
    // Access metadata when available
    const owner = this.cell_instance?.assignee_id
    const config = this.cell_instance?.initial_data
    const previousRuns = this.cell_instance?.fragments
    
    // Use context in execution
    const result = this.processWithContext(input, { owner, config })
    
    return {
      success: true,
      output: result,
      execution_time: 10
    }
  }
  // ... other methods
}
```

**Benefits:**
- ✅ Access to owner/assignee information (`assignee_id`)
- ✅ Access to initial configuration (`initial_data`)
- ✅ Access to execution history (`fragments`)
- ✅ Access to file references (`refs`)
- ✅ Backward compatible (optional field)

**Python Example:**
```python
from typing import Optional, Dict, Any
from app.core.base_cell import BaseCell, CellResult
from app.models.content import Cell

class DataProcessingCell(BaseCell):
    def __init__(self, cell_instance: Optional[Cell] = None):
        super().__init__(cell_instance)
        # self.cell_instance is now available
    
    async def execute(self, input: Dict[str, Any]) -> CellResult:
        # Access metadata when available
        owner = self.cell_instance.assignee_id if self.cell_instance else None
        config = self.cell_instance.initial_data if self.cell_instance else {}
        
        # Process with context
        result = self.process_with_context(input, owner=owner, config=config)
        
        return CellResult(
            success=True,
            output=result,
            execution_time=10
        )
```

### Key Concepts

**CellResult** - What your `execute()` must return:
```typescript
{
  success: boolean           // Whether execution succeeded
  output: Record<string, any> // The result data
  execution_time: number     // How long it took (ms)
  error?: string            // Error message if failed
  artifacts?: string[]      // R2/S3 artifact URLs if any
  fragments?: Fragment[]    // Execution trace (optional)
}
```

**CellMetadata** - What your `describe()` must return:
```typescript
{
  id: string                // Unique identifier ('my-cell-type')
  name: string              // Human-readable name
  version: string           // SemVer version ('1.0.0')
  description: string       // What the cell does
  inputs: Record<string, any>  // Input schema
  outputs: Record<string, any> // Output schema
  tags: string[]            // Categories ('image', 'data', etc)
}
```

**ValidationError** - What `validate()` returns:
```typescript
[
  { field: 'fieldName', message: 'Error description' }
]
```

## 🚨 MANDATORY REQUIREMENTS CHECKLIST

Before starting any cell implementation, your cell MUST satisfy all of these:

- [ ] **Implements `BaseCell` interface** - Not negotiable
- [ ] **Implements `execute(input)`** - Executes the cell's main logic
- [ ] **Implements `describe()`** - Returns CellMetadata with id, name, version, inputs, outputs
- [ ] **Implements `validate(input)`** - Validates input and returns ValidationError[]
- [ ] **Creates type.json** - Cell type definition with symlink
- [ ] **TypeScript for frontend** - All new frontend code uses TypeScript
- [ ] **Documentation included** - `docs/README.md` with usage examples
- [ ] **Tests included** - 90%+ coverage for backend and frontend

**If your cell doesn't implement BaseCell, it will be rejected in code review. Period.**

---

## Quick Start

### 1. Create Cell Type Directory

Create a new directory under `artifacts/canonical/cell_types/`:

```bash
mkdir -p artifacts/canonical/cell_types/my-cell-type/{backend/scripts,backend/tests,frontend/tests,docs}
```

### 2. Create Notebook Item Type Definition

**IMPORTANT**: Cell types follow a symlink architecture where the canonical type definition lives in `artifacts/canonical/notebook_item_types/` and is symlinked from the cell type directory.

#### Step 2.1: Create the canonical type definition

Create `artifacts/canonical/notebook_item_types/my-cell-type.json`:

```json
{
  "id": "my-cell-type",
  "name": "My Cell Type",
  "description": "Description of what this cell does",
  "version": "1.0.0",
  "category": "data-processing",
  "can_render_dynamically": false,
  "default_refs": {
    "view": ["frontend/View.vue"],
    "basecell": ["frontend/MyCellType.ts"],
    "scripts": ["backend/scripts/main.py"],
    "docs": ["docs/README.md"]
  },
  "default_initial_data": {
    "category": "ephemeral",
    "param1": "default_value",
    "param2": 100
  },
  "allow_instance_override_refs": true,
  "properties_schema": {
    "category": {
      "type": "string",
      "default": "ephemeral",
      "description": "Cell category - 'ephemeral' marks this as ephemeral (not persisted)"
    },
    "param1": {
      "type": "string",
      "default": "default_value",
      "description": "First parameter"
    },
    "param2": {
      "type": "integer",
      "default": 100,
      "description": "Second parameter"
    }
  }
}
```

**Note on Ephemeral Cells**: If your cell should NOT persist in the database (recommended for debugging/utility cells), include `"category": "ephemeral"` in both `default_initial_data` and `properties_schema` as shown above.

> **🚨 `basecell` ref is REQUIRED**: The `"basecell"` entry in `default_refs` must point to your cell's TypeScript file that implements `BaseCell`. This is how `useCellViewProvider` locates your cell implementation at runtime. Without it, the cell will fail to load with: `[useCellViewProvider] Cell type "<id>" has no basecell ref in type.json`. See [`artifacts/canonical/notebook_item_types/calculator-cell.json`](../artifacts/canonical/notebook_item_types/calculator-cell.json) for a reference.

#### Step 2.2: Create the symlink

Create a symlink from the cell type directory to the canonical definition:

```bash
cd artifacts/canonical/cell_types/my-cell-type
ln -s ../../notebook_item_types/my-cell-type.json type.json
```

Verify the symlink was created correctly:

```bash
ls -la type.json  # Should show: type.json -> ../../notebook_item_types/my-cell-type.json
readlink type.json  # Should output: ../../notebook_item_types/my-cell-type.json
```

### 3. Create Backend Script (Optional)

Create `artifacts/canonical/cell_types/my-cell-type/backend/scripts/main.py`:

```python
"""
Main execution logic for my-cell-type.
"""

from typing import Dict, Any

def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the cell.
    
    Args:
        cell_data: Cell instance data
        
    Returns:
        Dict with execution results
    """
    param1 = cell_data.get('param1', 'default_value')
    param2 = cell_data.get('param2', 100)
    
    # Your cell logic here
    result = f"Processed: {param1} with {param2}"
    
    return {
        "success": True,
        "output": result
    }
```

### 4. Create Frontend Implementation (TypeScript + BaseCell)

**Note**: All new frontend code must use TypeScript. New cells should implement the `BaseCell` interface.

**Option A: Simple Rendering Component** (`View.vue`)

Create `artifacts/canonical/cell_types/my-cell-type/frontend/View.vue` for UI rendering:

**Option B: Full BaseCell Implementation** (Recommended)

Create `artifacts/canonical/cell_types/my-cell-type/frontend/MyCell.ts` that implements `BaseCell`:

```typescript
// MyCell.ts
import type { BaseCell, CellResult, CellMetadata, ValidationError, EnvironmentConfig } from '@/types/BaseCell'

export class MyCellType extends BaseCell {
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      const param1 = input.param1 || 'default'
      const param2 = input.param2 || 100

      // Your cell logic here
      const result = `Processed: ${param1} with ${param2}`

      return {
        success: true,
        output: { result },
        execution_time: performance.now() - startTime
      }
    } catch (error) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error instanceof Error ? error.message : 'Unknown error'
      }
    }
  }

  async describe(): Promise<CellMetadata> {
    return {
      id: 'my-cell-type',
      name: 'My Cell Type',
      version: '1.0.0',
      description: 'Description of what this cell does',
      inputs: {
        param1: { type: 'string', description: 'First parameter', required: true },
        param2: { type: 'number', description: 'Second parameter', required: false }
      },
      outputs: {
        result: { type: 'string', description: 'The result' }
      },
      tags: ['data-processing', 'utility']
    }
  }

  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.param1) {
      errors.push({ field: 'param1', message: 'param1 is required' })
    }

    return errors
  }

  async setup?(config: any): Promise<void> {
    // Optional: Initialize resources
    console.log('Cell setup called with config:', config)
  }

  async teardown?(): Promise<void> {
    // Optional: Cleanup resources
    console.log('Cell teardown called')
  }

  async health_check?() {
    return {
      status: 'healthy',
      can_execute: true
    }
  }
}
```

Then create the Vue rendering component for the UI:

Create `artifacts/canonical/cell_types/my-cell-type/frontend/View.vue`:

**Role of View.vue**: Renders the cell UI in the workspace. Connected to your BaseCell class via the cell instance.

```vue
<template>
  <div class="my-cell-type bg-surface border border-border rounded-lg p-4">
    <h3 class="text-lg font-semibold mb-3">My Cell Type</h3>

    <!-- Display current cell data -->
    <div v-if="cellInstance" class="mb-4">
      <p class="text-sm text-gray-600">Status: {{ cellInstance.health_check ? 'Healthy' : 'Unknown' }}</p>
    </div>

    <div class="space-y-2">
      <div>
        <label class="block text-sm font-medium mb-1">Parameter 1</label>
        <input
          v-model="param1"
          type="text"
          class="w-full px-3 py-2 border rounded"
          placeholder="Enter param1"
          @change="onParamChange"
        />
      </div>

      <div>
        <label class="block text-sm font-medium mb-1">Parameter 2</label>
        <input
          v-model.number="param2"
          type="number"
          class="w-full px-3 py-2 border rounded"
          placeholder="Enter param2"
          @change="onParamChange"
        />
      </div>

      <!-- Execute button for headless execution -->
      <button
        @click="executeCell"
        class="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        :disabled="isExecuting"
      >
        {{ isExecuting ? 'Executing...' : 'Execute' }}
      </button>

      <!-- Show execution result -->
      <div v-if="lastResult" class="mt-4 p-2 bg-gray-100 rounded">
        <p class="text-sm"><strong>Result:</strong> {{ lastResult.output.result }}</p>
        <p class="text-xs text-gray-600">Execution time: {{ lastResult.execution_time }}ms</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, type Ref } from 'vue'
import type { BaseCell, CellResult } from '@/types/BaseCell'
import { MyCellType } from './MyCell'

// Define props interface
interface Props {
  cell: {
    id?: string
    initial_data?: {
      param1?: string
      param2?: number
    }
  }
}

const props = defineProps<Props>()

// Typed emits
const emit = defineEmits<{
  'update:cell': [cell: Props['cell']]
}>()

// Typed refs
const param1: Ref<string> = ref(props.cell.initial_data?.param1 || '')
const param2: Ref<number> = ref(props.cell.initial_data?.param2 || 100)
const isExecuting: Ref<boolean> = ref(false)
const lastResult: Ref<CellResult | null> = ref(null)
const cellInstance: Ref<BaseCell | null> = ref(null)

// Initialize BaseCell instance
onMounted(async () => {
  cellInstance.value = new MyCellType()
  if (cellInstance.value.setup) {
    await cellInstance.value.setup({ headless_mode: true })
  }
})

// Watch for prop changes
watch(() => props.cell.initial_data, (newData) => {
  if (newData) {
    param1.value = newData.param1 || param1.value
    param2.value = newData.param2 || param2.value
  }
}, { deep: true })

// Update cell data on input change
function onParamChange(): void {
  emit('update:cell', {
    ...props.cell,
    initial_data: {
      ...props.cell.initial_data,
      param1: param1.value,
      param2: param2.value
    }
  })
}

// Execute cell via BaseCell interface
async function executeCell(): Promise<void> {
  if (!cellInstance.value) return

  isExecuting.value = true
  try {
    lastResult.value = await cellInstance.value.execute({
      param1: param1.value,
      param2: param2.value
    })
  } catch (error) {
    console.error('Cell execution error:', error)
  } finally {
    isExecuting.value = false
  }
}
</script>
```

**Key TypeScript Elements**:
- `lang="ts"` on script tag
- `interface Props` for typed props
- `type` imports for Vue types and BaseCell interface
- Typed refs with `Ref<T>`
- Typed emit with tuple syntax
- Return type annotations (`:void`, `:Promise<void>`)
- BaseCell instance initialization and usage

### 5. Create Documentation

Create `artifacts/canonical/cell_types/my-cell-type/docs/README.md`:

```markdown
# My Cell Type

## Overview

Brief description of what this cell type does.

## Properties

### param1 (string)
- Description of param1
- Default: "default_value"

### param2 (integer)
- Description of param2
- Default: 100

## Usage

Example usage instructions...
```

### 6. Verify Your Cell Type

The cell type will be **automatically discovered** on server startup and made available in the frontend. No manual steps are required!

**Backend Startup:** When the backend starts, it automatically:
1. Scans `artifacts/canonical/cell_types/` for all `type.json` files
2. Discovers and validates each cell type
3. Syncs discovered types to the database
4. Makes them immediately available via API endpoints

**Frontend:** Cell types are automatically available when fetching from `/api/cells/types/list`

**For Development (Optional):** If you add a new cell type while the server is running, you can trigger re-discovery without restarting:

```bash
curl -X POST http://localhost:8000/api/v1/notebook-item-types/registry/discover \
  -H "Authorization: Bearer YOUR_TOKEN"
```

This will re-scan the filesystem and automatically sync any new types to the database.

## Directory Structure Reference

Complete structure for a cell type:

```
my-cell-type/
├── type.json                    # REQUIRED: Cell type definition
├── backend/                     # Optional: Backend components
│   ├── workflow.yaml            # Optional: LangGraph workflow
│   ├── scripts/                 # Optional: Python scripts
│   │   ├── __init__.py
│   │   ├── main.py              # Main execution logic
│   │   └── utils.py             # Helper functions
│   └── tests/                   # Recommended: Backend tests
│       ├── __init__.py
│       └── test_main.py
├── frontend/                    # Optional: Frontend components
│   ├── View.vue                 # Cell rendering component (TypeScript)
│   ├── composables.ts           # Optional: Vue composables (TypeScript)
│   ├── store.ts                 # Optional: Pinia store (TypeScript)
│   └── tests/                   # Recommended: Frontend tests
│       └── View.spec.ts
└── docs/                        # REQUIRED: Documentation
    └── README.md
```

## Best Practices

### 0. CRITICAL: Vue 3 Reactivity Isolation (Buffer Local Pattern)

⚠️ **MANDATORY for all Vue components with dynamic props**

When building cell View components, always follow the **Buffer Local Pattern** to avoid "reactivity shadowing":

**The Pattern**:
1. **Hydration**: Read from `props.cell` only on `onMounted`
2. **Buffer Local**: Use flat `ref` variables for all user interactions (e.g., `const localInput = ref('')`)
3. **Persistence**: Sync to `cellInstance` only on explicit actions (save/generate)

**Why It Matters**: Dynamic cells receive props that can change unpredictably. Cascading computeds + deeply nested props = lost reactivity tracking. Local refs protect your UI state.

**Quick Example**:
```typescript
// ❌ WRONG: Cascading computeds lose reactivity
const inputImage = computed(() => props.cell?.data?.image || '')
const displayImage = computed(() => inputImage.value)

// ✅ RIGHT: Simple, protected UI state
const localPreview = ref(props.cell?.data?.image || '')
const displayImage = computed(() => {
  if (localPreview.value) return localPreview.value
  return props.cell?.data?.image || ''
})
```

**See**: [`REACTIVITY_ISOLATION.md`](./REACTIVITY_ISOLATION.md) for complete patterns, pitfalls, and checklist.

---

### 0.1 NEVER Create Custom Endpoints - Use Existing API

**Rule**: Every cell execution must use **existing endpoints only**. Zero exceptions.

**Available Endpoints**:
- Regular cells (persisted): `POST /api/cells/{cell_id}/execute`
- Ephemeral cells (utility): `POST /api/cells/execute-ephemeral`

**Why Not Custom Endpoints**:
- ❌ Breaks architectural consistency (every cell should follow same pattern)
- ❌ Violates RULESET.md (modular, reusable code)
- ❌ Makes headless-first execution impossible
- ❌ Creates unmaintainable duplicate endpoint code

**Correct Implementation** ✅:

For **regular cells** with `cell_id`:
```typescript
import { apiFetch } from '@/services/apiService'

export class MyCell implements BaseCell {
  async execute(input: Record<string, any>): Promise<CellResult> {
    // Use apiFetch instead of fetch - adds auth headers automatically
    const response = await apiFetch(`/api/cells/${cellId}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ parameters: input })
    })
    const result = await response.json()
    return { success: result.success, output: result.data, execution_time: 0 }
  }
}
```

For **ephemeral cells** (no `cell_id`, utility):
```typescript
import { apiFetch } from '@/services/apiService'

export class UtilityCell implements BaseCell {
  async execute(input: Record<string, any>): Promise<CellResult> {
    // Use apiFetch for automatic auth header handling
    const response = await apiFetch('/api/cells/execute-ephemeral', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        cell_type: 'my-utility-cell-type',
        input_data: input
      })
    })
    const result = await response.json()
    return { success: result.result.success, output: result.result.data, execution_time: 0 }
  }
}
```

**How It Works**: The endpoint automatically:
1. Finds your cell's canonical type definition in `artifacts/canonical/cell_types/{cell_type_id}/`
2. Dynamically loads your `backend/scripts/main.py`
3. Calls your `execute_cell(cell_data)` function
4. Returns result

You provide **zero custom routing code**. The platform handles it.

---

### 0.5. ALWAYS Use `apiFetch` for Authentication

**Rule**: Never use plain `fetch()` for API calls. Always use `apiFetch` from `apiService.js`.

**Why**:
- ❌ Plain `fetch()` = 401 Unauthorized errors (missing Authorization header)
- ❌ No automatic token refresh on expiration
- ❌ No retry logic for transient auth failures
- ✅ `apiFetch` = Automatic auth header injection, 401 handling, token refresh, retry

**Correct Pattern** ✅:
```typescript
import { apiFetch } from '@/services/apiService'

export class MyCell implements BaseCell {
  async execute(input: Record<string, any>): Promise<CellResult> {
    // Always use apiFetch instead of fetch
    const response = await apiFetch('/api/cells/execute-ephemeral', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
        // Do NOT manually add Authorization - apiFetch does this automatically
      },
      body: JSON.stringify({
        cell_type: 'my-cell-type',
        input_data: input
      })
    })
    const result = await response.json()
    return result
  }
}
```

**What `apiFetch` Does Automatically**:
1. Gets current auth token via `authService.getAuthHeaders()`
2. Injects `Authorization: Bearer <token>` header
3. Detects 401 (Unauthorized) responses
4. Attempts token refresh via `authService.refreshSession()`
5. Retries request with new token if refresh succeeds
6. Clears auth and throws SessionExpiredError if refresh fails

**Common Error - WRONG** ❌:
```typescript
// This will fail with 401 Unauthorized because no auth header
const response = await fetch('/api/cells/execute-ephemeral', {
  method: 'POST',
  body: JSON.stringify({ ... })
})
```

---

### 1. Keep Files Under 500 Lines

Per RULESET.md Rule 1.1, no file should exceed 500 lines. Split large files into modules.

### 2. Use Semantic Naming

- Directory name: `kebab-case` (e.g., `sentiment-analysis`)
- Type ID: matches directory name
- View component: always `View.vue`
- Main script: always `main.py`

### 3. Use TypeScript for Frontend Code

**Required**: All new frontend code must use TypeScript per RULESET.md Rule 4.5.

- Use `<script setup lang="ts">` in Vue components
- Create `.ts` files for composables and stores
- Define explicit type interfaces
- Type all refs, props, and emits
- Use `type` imports for type-only dependencies

**See**: [TECHNICAL_GUIDE.md](../issues/1385/TECHNICAL_GUIDE.md) for comprehensive TypeScript patterns and [RULESET.md Rule 4.5](./RULESET.md#45-typescript-for-new-frontend-code) for requirements.

### 4. Provide Complete Documentation

Each cell type MUST have a `docs/README.md` with:
- Overview
- Properties and their types
- Usage examples
- References to components

### 5. Write Tests

Include tests for:
- Backend: `backend/tests/test_main.py`
- Frontend: `frontend/tests/View.spec.ts` (TypeScript)

Target 90%+ coverage.

### 6. Use Type Validation

Define `properties_schema` in `type.json` to document expected properties and their types.

## Testing Your Cell Type

### Backend Tests

```bash
cd backend
poetry run pytest artifacts/canonical/cell_types/my-cell-type/backend/tests/
```

### Frontend Tests

```bash
cd cockpit-vue
npm test -- artifacts/canonical/cell_types/my-cell-type/frontend/tests/
```

### Manual Testing

1. Start the backend server
2. Create a cell instance via API or UI
3. Verify the cell renders correctly
4. Test cell interactions

## Composing Other Cells (Two Valid Patterns)

Cells can interact with other cells in two ways:

### Pattern 1: Direct Cell-to-Cell Calls (Utility/Helper Pattern)
For simple operations or utility functions, cells can directly call other cells as functions:

```typescript
import type { BaseCell, CellResult } from '@/types/BaseCell'
import { CalculatorCell } from '@/cells/calculator-cell'

export class ComplexCell extends BaseCell {
  private calculatorCell: BaseCell

  async setup(config: any): Promise<void> {
    this.calculatorCell = new CalculatorCell()
    await this.calculatorCell.setup(config)
  }

  async execute(input: Record<string, any>): Promise<CellResult> {
    // Call another cell's execute
    const calcResult = await this.calculatorCell.execute({
      operation: 'add',
      a: 5,
      b: 3
    })

    if (!calcResult.success) {
      return { success: false, output: {}, execution_time: 0, error: 'Calculator failed' }
    }

    // Use the result in your logic
    const finalResult = (calcResult.output.result as number) * 2

    return {
      success: true,
      output: { result: finalResult },
      execution_time: performance.now()
    }
  }

  async describe() {
    return {
      id: 'complex-cell',
      name: 'Complex Cell',
      version: '1.0.0',
      description: 'Uses calculator cell internally',
      inputs: {},
      outputs: { result: { type: 'number' } },
      tags: ['composition']
    }
  }

  validate(input: Record<string, any>) {
    return []
  }

  async teardown(): Promise<void> {
    if (this.calculatorCell.teardown) {
      await this.calculatorCell.teardown()
    }
  }
}
```

### Pattern 2: Book-Based Orchestration (Recommended for Complex Workflows)
If you need to compose multiple cells into a complex workflow with explicit dependency management and parallelization, use **Books** instead. See [ADDING_NEW_BOOK_TYPE.md](./ADDING_NEW_BOOK_TYPE.md).

**Architecture Flexibility**:
- Use **direct cell-to-cell calls** for simple utility operations or helpers
- Use **Books** for complex multi-step workflows with explicit orchestration
- Both patterns are valid; choose based on your use case

## Advanced Features

### Custom Workflows

Add a LangGraph workflow definition:

```yaml
# backend/workflow.yaml
name: my-cell-workflow
nodes:
  - id: process
    type: function
    function: execute_cell
edges:
  - from: START
    to: process
```

### Custom Composables (TypeScript)

Create reusable Vue logic with explicit types:

```typescript
// frontend/composables.ts
import { ref, computed, type Ref, type ComputedRef } from 'vue'

// Define return type interface
export interface UseMyCellFeatureReturn {
  data: Ref<string>
  processedData: ComputedRef<string>
  processData: () => Promise<void>
}

export function useMyCellFeature(): UseMyCellFeatureReturn {
  const data = ref<string>('')
  
  const processedData = computed<string>(() => data.value.toUpperCase())
  
  async function processData(): Promise<void> {
    // Processing logic
  }
  
  return { data, processedData, processData }
}
```

### Isolated State Management (TypeScript)

Create a typed Pinia store:

```typescript
// frontend/store.ts
import { defineStore } from 'pinia'
import { ref, computed, type Ref } from 'vue'

interface CellData {
  value: string
  timestamp: number
}

export const useMyCellStore = defineStore('my-cell', () => {
  // Typed state
  const cellData = ref<CellData | null>(null)
  const isLoading = ref<boolean>(false)
  
  // Typed getters
  const hasData = computed<boolean>(() => cellData.value !== null)
  
  // Typed actions
  function updateData(newData: CellData): void {
    cellData.value = newData
  }
  
  return { cellData, isLoading, hasData, updateData }
})
```

## TypeScript Best Practices for Cells

Essential TypeScript patterns for cell implementation:

**1. Type All Refs**: `const messages = ref<Message[]>([])`, `const count = ref<number>(0)`

**2. Type-Only Imports**: `import type { CellData } from '@/types/cells'`

**3. Event Handlers**: `function handleClick(event: MouseEvent): void { }`

**4. Nullable Guards**: Check nullable refs before use: `if (element.value) { }`

**Complete patterns**: See [TECHNICAL_GUIDE.md](../issues/1385/TECHNICAL_GUIDE.md) and [RULESET.md Rule 4.5](./RULESET.md#45-typescript-for-new-frontend-code).

## Validation

Validate your cell type references:

```bash
curl http://localhost:8000/api/v1/notebook-item-types/registry/my-cell-type/validate \
  -H "Authorization: Bearer YOUR_TOKEN"
```

This returns a map of referenced files and whether they exist.

## Common Issues

### ⛔ Cell Created Custom Endpoint (WILL BE REJECTED)

**Symptom**: Cell backend has a custom router/endpoint like `/api/my-cell/process`

**Problem**:
- Breaks architectural pattern (every cell should use same endpoints)
- Creates technical debt (unmaintainable)
- Violates RULESET.md consistency requirement
- Makes headless execution impossible

**Fix**: Delete your custom endpoint and use existing `/api/cells/execute-ephemeral` or `/api/cells/{id}/execute`

**Example - WRONG ❌**:
```python
# DON'T DO THIS
from fastapi import APIRouter

router = APIRouter(prefix="/my-cell")

@router.post("/process")
async def process_cell(...):
    ...
```

**Example - CORRECT ✅**:
```typescript
// DO THIS INSTEAD
import { apiFetch } from '@/services/apiService'

export class MyCell extends BaseCell {
  async execute(input: Record<string, any>): Promise<CellResult> {
    // Use apiFetch - automatically adds auth headers and handles 401 errors
    const response = await apiFetch('/api/cells/execute-ephemeral', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        cell_type: 'my-cell-type',
        input_data: input
      })
    })
    // apiFetch ensures Authorization header is included and automatically retries on 401
    const result = await response.json()
    return result
  }
}
```

The `/api/cells/execute-ephemeral` endpoint handles routing to your cell's backend script automatically based on `cell_type`. No custom endpoint needed.

⚠️ **IMPORTANT**: Always use `apiFetch` instead of `fetch` for API calls. It automatically:
- Adds `Authorization: Bearer <token>` headers
- Detects 401 (Unauthorized) errors
- Attempts token refresh automatically
- Retries the request with the new token
- Clears auth if refresh fails

---

### ⛔ Cell Does Not Implement BaseCell (WILL BE REJECTED)

**This is the #1 reason cells are rejected in code review.**

**Symptom**: Your cell has functions like `execute_cell()` but not a class implementing `BaseCell`.

**Fix**:
1. Create a class that implements `BaseCell`
2. Move your logic into the three required methods
3. Return `CellResult`, `CellMetadata`, `ValidationError[]` types

**Example - WRONG ❌**:
```python
def execute_cell(cell_data):
    return {"success": True}  # ❌ Not BaseCell
```

**Example - RIGHT ✅**:
```python
class MyCell(BaseCell):
    async def execute(self, input):
        return CellResult(success=True, output={}, execution_time=10)

    async def describe(self):
        return CellMetadata(id='my-cell', name='My Cell', ...)

    def validate(self, input):
        return []  # No validation errors
```

**No exceptions. Every cell must implement BaseCell.**

---

### ⚠️ HTTP 401 Unauthorized Error on API Calls

**Symptom**: Backend returns `HTTP error 401: Unauthorized` when cell tries to execute via API

**Root Cause**: Using `fetch()` directly instead of `apiFetch()` - missing Authorization header

**Example - WRONG ❌**:
```typescript
// This fails with 401 because no Authorization header is sent
const response = await fetch('/api/cells/execute-ephemeral', {
  method: 'POST',
  body: JSON.stringify({
    cell_type: 'my-cell-type',
    input_data: input
  })
})
```

**Fix** ✅:
```typescript
import { apiFetch } from '@/services/apiService'

// Always use apiFetch - it adds Authorization header automatically
const response = await apiFetch('/api/cells/execute-ephemeral', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    cell_type: 'my-cell-type',
    input_data: input
  })
})
```

**What to Check**:
- [ ] Importing `apiFetch` from `@/services/apiService`?
- [ ] Using `apiFetch()` instead of `fetch()` for all API calls?
- [ ] Not manually adding Authorization header (apiFetch does this)?
- [ ] Using `Content-Type: application/json` header?

**How apiFetch Handles Auth**:
1. Automatically injects `Authorization: Bearer <token>` from localStorage
2. If 401 is returned, attempts to refresh token via backend
3. Retries the original request with new token
4. If refresh fails, clears auth data and throws SessionExpiredError

See [Best Practice 0.5: Always Use apiFetch](#05-always-use-apifetch-for-authentication) for detailed guidance.

---

### Cell Type Not Discovered

- Ensure `type.json` exists in the cell type directory
- Check JSON syntax is valid
- Verify `id` and `name` fields are present
- Restart the backend server or trigger re-discovery

### View Not Loading

- Check import path in browser console
- Verify `View.vue` exists at the correct path
- Ensure component exports are correct
- Check for syntax errors in Vue component
- **TypeScript**: Verify `lang="ts"` attribute is present

### TypeScript Type Errors

- Run `npm run type-check` in `cockpit-vue/` to see all errors
- Ensure all refs have explicit type annotations
- Use `type` imports for type-only dependencies
- Check `tsconfig.json` has strict mode enabled
- See [TECHNICAL_GUIDE.md](../issues/1385/TECHNICAL_GUIDE.md) for common solutions

### References Not Resolving

- Paths in `default_refs` are relative to cell type directory
- Use forward slashes (/) not backslashes
- Don't include leading slash

## Example: Sentiment Analysis Cell

See `artifacts/canonical/cell_types/example/` for a complete reference implementation.

## Support and References

**TypeScript Implementation**:
- **[TECHNICAL_GUIDE.md (Issue #1385)](../issues/1385/TECHNICAL_GUIDE.md)** - Complete TypeScript patterns and migration guide
- **[RULESET.md Rule 4.5](./RULESET.md#45-typescript-for-new-frontend-code)** - TypeScript requirements and standards

**Cell Architecture**:
- Check existing cell types in `artifacts/canonical/cell_types/` for examples
- Review technical specification: `docs/issues/949/technical-specification.md`

**General Support**:
- Contact the development team

---

## 🚨 FINAL REMINDER: BaseCell is NOT Optional

If you're creating a new cell, here's the ONE THING you need to remember:

**Your cell MUST implement the BaseCell interface.**

Not "should". Not "preferably". **MUST.**

- If you skip this, your PR will be rejected.
- If you implement it, your cell will work with the headless-first architecture.
- If you have questions, refer to the [BaseCell Interface (MANDATORY)](#basecel-interface-mandatory) section.

This is the architectural requirement that enables:
- ✅ Headless execution (scripts, automation, agents)
- ✅ Composition into Books (orchestrators)
- ✅ Consistency across all cells
- ✅ Future extensibility

---

**Last Updated**: 2025-12-14
**Version**: 1.0.1 - Added explicit BaseCell mandatory requirements
