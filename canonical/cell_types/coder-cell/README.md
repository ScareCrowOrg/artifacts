---
processed: true
processed_date: 2026-02-06
themes:
  - code-generation
  - automation
  - validation
modules:
  - coder-cell
code_verified: false
---

# ⚙️ CoderCell - Autonomous Code Generation Cell

## Overview

CoderCell is an autonomous code generation cell that creates new cells based on validated plans from PlannerCell. It uses **Aider + Qwen** to generate type.json definitions, TypeScript implementations, and Vue components with automatic validation and registry updates.

## Purpose

Generate missing cells identified by PlannerCell by:
1. Receiving validated plan with cell specifications
2. Generating type.json following schema
3. Generating TypeScript Cell.ts implementing BaseCell
4. Generating Vue View.vue component
5. Validating TypeScript compilation and JSON schema
6. Updating CellRegistry with new cells

## Key Features

- **🤖 AI-Powered Generation**: Uses Aider + Qwen (14B) via aider-worker
- **✅ Validation**: TypeScript compilation + JSON schema validation
- **📦 Pattern Following**: Uses existing cells as reference
- **🔄 Registry Integration**: Auto-updates CellRegistry after generation
- **🛡️ Error Handling**: Retry logic for transient failures
- **📝 Documentation**: Generates README.md for each cell

## Architecture

### Inputs

```typescript
{
  plan: DAGDefinition;         // From PlannerCell output
  context: {
    repo_structure: string;
    example_cells: Cell[];     // Reference cells
    constraints?: string[];
  };
}
```

### Outputs

```typescript
{
  success: boolean;
  files_created: string[];     // Paths of created files
  validation: {
    passed: boolean;
    errors?: string[];
  };
  execution_time: number;
}
```

## Backend Integration

- **aider-worker `/execute` endpoint**: Code generation via Aider + Qwen
- **TypeScript Compiler**: Validation of generated .ts files
- **JSON Schema Validator**: Validation of type.json
- **CellRegistry**: Auto-refresh after successful generation

## Frontend Components

- **CoderCell.ts**: Implements BaseCell interface
- **View.vue**: Displays generated files, validation results, code preview
- **types.ts**: TypeScript type definitions

## Workflow

```
Validated Plan (from PlannerCell)
    ↓
[CoderCell]
  ├─ Load example cells as reference
  ├─ Call aider-worker /execute
  │  ├─ Generate type.json
  │  ├─ Generate Cell.ts (BaseCell)
  │  ├─ Generate View.vue
  │  └─ Generate README.md
  ├─ Validate TypeScript compilation
  ├─ Validate JSON schema
  ├─ IF valid:
  │  └─ Update CellRegistry
  └─ Return result
```

## Generated File Structure

For each new cell, CoderCell generates:

```
artifacts/canonical/cell_types/{cell-name}/
├── type.json              # Cell type definition
├── README.md             # Documentation
├── frontend/
│   ├── {CellName}.ts    # BaseCell implementation
│   ├── View.vue         # Vue component
│   └── types.ts         # TypeScript types
└── backend/             # If needed
    └── scripts/
        └── main.py
```

## Code Generation Patterns

### 1. type.json
- Follows NotebookItemType schema
- Includes discovery fields
- Proper version and category

### 2. Cell.ts
- Extends BaseCell
- Implements required methods
- Type-safe props

### 3. View.vue
- Vue 3 Composition API
- Uses Tailwind CSS
- Responsive design
- Accessibility (ARIA labels)

## Validation Steps

1. **Syntax Check**: TypeScript compilation without errors
2. **Schema Validation**: type.json matches schema
3. **Import Check**: All imports resolve correctly
4. **Smoke Test**: Cell instantiates without errors

## Example Use Cases

1. **Auto-Rigging Cell**: Generate cell for automatic 3D model rigging
2. **Animation Generator**: Create cell for generating character animations
3. **Texture Processor**: Generate cell for texture optimization
4. **Sound Effect Generator**: Create cell for generating horror sound effects

## Testing Strategy

- Unit tests: File generation, validation logic
- Integration tests: End-to-end with aider-worker
- Validation tests: TypeScript + JSON schema
- Registry tests: Auto-refresh functionality
- Success rate target: 80%+ valid cells

## Error Handling

### Transient Errors
- Retry up to 3 times with exponential backoff
- Log attempts for debugging

### Permanent Errors
- Return detailed error information
- Suggest manual intervention
- Preserve partial results for debugging

## Related Components

- **PlannerCell**: Provides specifications for cells to generate
- **aider-worker**: Executes Aider for code generation
- **CellRegistry**: Tracks available cells
- **MITM Gate**: May request approval before generation

## Configuration

Default configuration in `type.json`:
- `estimated_duration_seconds`: 60
- `required_resources`: ["aider-worker", "typescript-compiler", "cell-registry"]

## Aider Integration Details

### Model
- **Primary**: Qwen 2.5 Coder 14B (via Ollama)
- **Fallback**: GPT-4 (if Qwen unavailable)

### Commands
```bash
aider --model qwen2.5-coder:14b \
      --yes \
      --auto-commits \
      --file artifacts/canonical/cell_types/{cell-name}/type.json \
      --file artifacts/canonical/cell_types/{cell-name}/frontend/Cell.ts
```

## Status

- **Version**: 1.0.0
- **Phase**: Phase 3 (Planning) - Issue 3.4-3.6
- **Status**: Definition complete (type.json, README.md exist). Code implementation (frontend/backend) is pending. Integration with Aider/Qwen will be established upon code completion.

## Next Steps

1. Implement backend logic with Aider integration (Issue 3.5)
2. Implement frontend components (Issue 3.6)
3. Integration tests with PlannerCell (Issue 3.7)
