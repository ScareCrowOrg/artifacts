---
processed: true
processed_date: 2026-02-06
themes:
  - planning
  - discovery
  - automation
modules:
  - planner-cell
code_verified: false
---

# 🧠 PlannerCell - Autonomous Planning Cell

## Overview

PlannerCell is an autonomous planning cell that transforms user intent into executable workflows through recursive discovery and planning. It uses a **loop-based architecture** with self-healing capabilities, learning from failures to improve subsequent attempts.

## Purpose

Transform natural language intent (e.g., "Create a horror boss with animations") into validated execution plans (DAG definitions) by:
1. Discovering available cells through 4-level search
2. Analyzing task complexity
3. Recursively decomposing complex tasks into manageable subplans
4. Generating execution DAGs
5. Identifying missing cells
6. Learning from previous failures

## Key Features

- **🔍 Multi-Level Discovery**: Uses DiscoveryService for 4-level cell discovery (semantic, label, LLM ranking, validation)
- **♻️ Recursive Planning**: Automatically decomposes complex tasks into simpler subplans
- **🛡️ Self-Healing**: Learns from failures via `previous_failure` context
- **🧩 Gap Detection**: Identifies missing cells and coordinates with CoderCell for generation
- **✅ Validation**: Validates DAG structure (no cycles, valid edges)
- **🎯 Confidence Scoring**: Returns confidence metrics (0-1) for generated plans

## Architecture

### Inputs

```typescript
{
  intent: string;              // "Create horror boss with animations"
  previous_failure?: {         // Context from retry
    error: string;
    what_failed: string;
    attempted_approach: string;
  };
}
```

### Outputs

```typescript
{
  success: boolean;
  plan: {
    cells_discovered: string[];        // ["png_gen", "sf3d", "blender"]
    cells_to_generate: CellSpec[];     // [{ name: "auto_rig", ... }]
    execution_dag: DAGDefinition;
    confidence: number;                // 0-1
    rationale: string;
  } | null;
  execution_time: number;
}
```

## Backend Integration

- **DiscoveryService**: 4-level cell search
- **OpenInterpreter**: Repository exploration and context gathering
- **Gemini Flash Lite**: Planning decisions and DAG generation
- **aider-worker `/interpret` endpoint**: Existing infrastructure reuse

## Frontend Components

- **PlannerCell.ts**: Implements BaseCell interface
- **View.vue**: Displays planning status, progress, and DAG visualization
- **types.ts**: TypeScript type definitions

## Workflow

```
User Intent
    ↓
[PlannerCell depth=0]
  ├─ Call DiscoveryService
  ├─ Analyze complexity
  ├─ IF complex:
  │  └─ Decompose into subplans (recursive)
  ├─ IF missing cells:
  │  └─ Generate specs for CoderCell
  └─ Return plan with confidence
    ↓
[MITM Gate] (human approval)
    ↓
[Execution or Refinement]
```

## Recursion & Loop Control

- **Max Depth**: Configurable (default: 5) to prevent infinite loops
- **Decomposition**: Complex tasks automatically broken into simpler subplans
- **Learning**: `previous_failure` context passed to improve retry attempts

## Example Use Cases

1. **Simple Task**: "Generate PNG logo" → Direct plan with existing cells
2. **Complex Task**: "Create 3D character with animations" → Decompose into subplans (visual, mesh, rig, animations)
3. **Missing Cells**: Detect gaps → Generate specs → Pass to CoderCell
4. **Failure Recovery**: Plan fails → Retry with `previous_failure` context

## Testing Strategy

- Unit tests: Discovery loop, decomposition logic, validation
- Integration tests: End-to-end with DiscoveryService
- Failure recovery tests: Previous_failure context handling
- Performance tests: < 30s for typical planning tasks

## Related Components

- **CoderCell**: Generates missing cells based on PlannerCell output
- **DiscoveryService**: Provides cell discovery capabilities
- **MITM Gate**: Human approval before execution
- **BookAdapter**: Executes the generated DAG

## Configuration

Default configuration in `type.json`:
- `max_depth`: 5 (maximum recursion depth)
- `estimated_duration_seconds`: 30
- `required_resources`: ["discovery-service", "llm-service", "aider-worker"]

## Status

- **Version**: 1.0.0
- **Phase**: Phase 3 (Planning) - Issue 3.1-3.3
- **Status**: Type definition complete, implementation pending

## Next Steps

1. Implement backend logic (Issue 3.2)
2. Implement frontend components (Issue 3.3)
3. Integration tests with CoderCell (Issue 3.7)
