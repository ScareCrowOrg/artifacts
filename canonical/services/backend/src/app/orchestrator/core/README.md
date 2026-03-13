---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - orchestrator
  - workflows
  - architecture
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Orchestrator Core Module

## Overview

The `orchestrator/core` module provides the main workflow execution orchestration for ScareVerse cells. It monitors the issues-queue, loads workflow definitions, executes workflows using LangGraph, and manages cell state transitions.

## Architecture

The module is organized into specialized components:

```
app/orchestrator/core/
├── __init__.py              # Public API exports
├── orchestrator.py          # Main facade class (178 lines)
├── state_manager.py         # Cell state management (116 lines)
├── workflow_executor.py     # Workflow execution logic (362 lines)
├── monitoring.py            # Queue monitoring & control (336 lines)
└── README.md               # This file
```

## Components

### Orchestrator (orchestrator.py)

Main facade class that provides a unified interface to all orchestrator functionality.

**Responsibilities:**
- Initialize orchestrator with agent and queue configuration
- Load agent and issues-queue book from database
- Delegate operations to specialized modules
- Maintain backward compatibility with legacy API

**Key Methods:**
- `__init__(agent_id)` - Initialize orchestrator with agent configuration
- `execute_cell_workflow(cell_id)` - Execute workflow for a specific cell
- `update_cell_state(cell_id, new_state, ...)` - Update cell state
- `start_monitoring()` - Start async monitoring loop
- `stop_monitoring()` - Stop monitoring loop
- `get_pending_cells()` - Get all PENDING cells

### StateManager (state_manager.py)

Handles cell state transitions and database updates.

**Responsibilities:**
- Update cell state in the database
- Publish state change events to event bus
- Extract outputs from workflow execution states
- Merge output data into cell data

**Key Methods:**
- `update_cell_state(cell_id, new_state, output_data, error_data)` - Update state with optional data
- `extract_outputs_from_state(final_state, cell_id)` - Extract outputs from workflow state

### WorkflowExecutor (workflow_executor.py)

Manages workflow execution strategies and orchestrates workflow runs.

**Responsibilities:**
- Execute cell workflows using multiple strategies:
  1. Custom Python graphs (*graph.py files)
  2. YAML workflow definitions
  3. Inline workflows from cell type
- Load and parse workflow definitions
- Handle PipelineItem conversions
- Manage workflow execution context

**Key Methods:**
- `execute_cell_workflow(cell_id)` - Main execution entry point
- `_execute_custom_graph(...)` - Execute via custom Python graph
- `_execute_langgraph_custom_graph(...)` - Execute via LangGraph custom graph
- `_execute_langgraph_workflow(...)` - Execute via standard LangGraph workflow
- `_load_workflow_from_yaml(cell_type)` - Load workflow from YAML file

### QueueMonitor (monitoring.py)

Handles queue monitoring, polling, and processing control.

**Responsibilities:**
- Monitor issues-queue for PENDING cells
- Control monitoring loop (start, stop, pause, resume)
- Support manual trigger for immediate processing
- Respect max concurrent cells configuration
- Provide async and sync monitoring loops

**Key Methods:**
- `start_monitoring()` - Start async monitoring loop
- `stop_monitoring()` - Stop monitoring loop
- `pause_processing()` - Pause cell processing
- `resume_processing()` - Resume cell processing
- `force_process_pending_issues()` - Trigger immediate processing
- `get_pending_cells()` - Query PENDING cells
- `monitor_queue_async()` - Async monitoring loop
- `monitor_queue()` - Sync monitoring loop

## Usage

### Basic Usage

```python
from app.orchestrator.core import Orchestrator

# Initialize orchestrator
orchestrator = Orchestrator(agent_id="main-workflow-orchestrator-v1")

# Start monitoring (async)
result = orchestrator.start_monitoring()
print(result)  # {"status": "started", "message": "..."}

# Get pending cells
pending = orchestrator.get_pending_cells()
print(f"Found {len(pending)} pending cells")

# Execute a specific cell workflow
success = orchestrator.execute_cell_workflow("cell-123")

# Stop monitoring
orchestrator.stop_monitoring()
```

### Advanced Usage

```python
# Pause/resume processing
orchestrator.pause_processing()
# ... do some maintenance work ...
orchestrator.resume_processing()

# Force immediate processing
result = orchestrator.force_process_pending_issues()
print(f"Triggered processing of {result['pending_count']} cells")

# Get monitoring status
status = orchestrator.get_monitoring_status()
print(f"Active: {status['active']}, Interval: {status['polling_interval']}s")

# Manual workflow execution
orchestrator.update_cell_state("cell-456", EstadoCelula.EXECUTANDO)
success = orchestrator.execute_cell_workflow("cell-456")
if success:
    orchestrator.update_cell_state("cell-456", EstadoCelula.FINALIZADO)
```

## Configuration

The orchestrator is configured via the agent's `agent_specific_config`:

```json
{
  "polling_interval_seconds": 5,
  "max_concurrent_cells": 2
}
```

**Configuration Parameters:**
- `polling_interval_seconds` (int, default: 5) - Seconds between polling cycles
- `max_concurrent_cells` (int, default: 2) - Maximum cells to process concurrently

## Workflow Execution Priority

The orchestrator executes workflows in the following priority order:

1. **Custom Python Graph** - If `*graph.py` file is referenced in `cell_type.python_refs`
   - Uses `importlib` to load and execute the graph
   - Expects an `execute(pipeline_item)` function
   - Returns `PipelineItem` with results

2. **YAML Workflow** - If `*workflow*.yml` file is referenced in `cell_type.yaml_refs`
   - Parses YAML workflow definition
   - Executes via standard LangGraph workflow

3. **Inline Workflow** - If `cell_type.workflows["main_workflow"]` is defined
   - Uses embedded workflow definition from cell type
   - Executes via standard LangGraph workflow

## Events Published

The orchestrator publishes the following events via the event bus:

- `cell_state_changed` - When cell state transitions
  - Payload: `{cell_id, new_state, cell_data}`
  
- `pipeline_fragments` - When new fragments are generated (via Redis)
  - Payload: Fragment data for real-time UI updates

## Error Handling

The orchestrator handles errors at multiple levels:

1. **Cell Not Found** - Returns `False`, logs error
2. **Cell Type Not Found** - Updates cell state to ERROR
3. **Agent Not Found** - Continues without agent context (warning logged)
4. **Workflow Execution Error** - Updates cell state to ERROR, stores error message
5. **State Update Error** - Logs error, returns `False`

## Dependencies

- `app.models` - Celula, TipoCelula, Agent, Livro, EstadoCelula
- `app.database` - Database operations
- `app.workflow_executor` - LangGraph workflow execution
- `app.event_bus` - Event publishing
- `app.orchestrator.helpers` - PipelineItem conversions

## Testing

Tests for this module are located in:
- `tests/unit/backend/orchestrator/` - Unit tests for each component
- `tests/integration/backend/orchestrator/` - Integration tests with database

Run tests:
```bash
pytest tests/unit/backend/orchestrator/ -v
```

## File Size Compliance

All files in this module are under 500 lines (Rule 1.1):
- `orchestrator.py`: 178 lines ✅
- `state_manager.py`: 116 lines ✅
- `workflow_executor.py`: 362 lines ✅
- `monitoring.py`: 336 lines ✅

**Total:** 992 lines across 4 modules (previously 798 lines in 1 file)

## Migration Guide

### Before (Monolithic)

```python
from app.orchestrator.core import Orchestrator

orchestrator = Orchestrator()
orchestrator.execute_cell_workflow("cell-123")
```

### After (Modularized)

```python
# Public API remains the same - no code changes needed!
from app.orchestrator.core import Orchestrator

orchestrator = Orchestrator()
orchestrator.execute_cell_workflow("cell-123")
```

The modularization is **fully backward compatible**. All existing code continues to work without modification.

## Internal Module Access (Advanced)

If you need direct access to specialized modules:

```python
from app.orchestrator.core.orchestrator import Orchestrator
from app.orchestrator.core.state_manager import StateManager
from app.orchestrator.core.workflow_executor import WorkflowExecutor
from app.orchestrator.core.monitoring import QueueMonitor

# Direct module usage (advanced)
state_manager = StateManager()
state_manager.update_cell_state("cell-123", EstadoCelula.FINALIZADO)
```

## Future Enhancements

- Add async workflow execution with asyncio tasks
- Implement workflow caching for repeated executions
- Add metrics and observability
- Support for distributed orchestration across multiple workers
- Workflow retry logic with exponential backoff

## References

- [RULESET.md](../../../RULESET.md) - Project rules
- [ARQUITETURA_TESTES.md](../../../docs/ARQUITETURA_TESTES.md) - Test architecture
- [workflow_executor.py](../../workflow_executor.py) - LangGraph workflow execution
- [event_bus.py](../../event_bus.py) - Event publishing
