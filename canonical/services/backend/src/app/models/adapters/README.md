---
processed: true
processed_date: 2026-02-10
themes:
  - backend
  - architecture
  - database
  - services
  - unified-runtime
modules:
  - backend
  - adapters
code_verified: true
dead_docs_found: false
---
# Adapter Classes for Notebook Items

This module implements the Adapter pattern for notebook items, providing execution logic while keeping pure data models clean and focused.

## Module Structure

```
adapters/
├── __init__.py                 # Public API exports
├── adapters_base.py            # NotebookItemAdapter base class (368 lines)
├── notebook_item_adapter.py    # UnifiedNotebookItemAdapter (498 lines) ⭐ NEW
├── adapters_cell.py            # CellAdapter - legacy wrapper (79 lines)
├── adapters_book.py            # BookAdapter - legacy wrapper (79 lines)
└── README.md                   # This file
```

## 🆕 Unified Runtime Architecture (Issue 0.3)

**New in February 2026**: This module now implements the unified adapter architecture that handles both cells and books through a single execution engine.

### Key Features
- ✅ **Unified Dispatch**: Single `UnifiedNotebookItemAdapter` handles both cells and books
- ✅ **Dual-Mode Execution**: Books support DAG, Script, and Hybrid execution modes
- ✅ **Hierarchical Tracing**: Tracks execution via `executed_by` field in fragments
- ✅ **Fragment Management**: Centralizes creation and updates of ExecutionFragments
- ✅ **Backward Compatible**: Legacy `CellAdapter` and `BookAdapter` work as thin wrappers

## Design Pattern

This module implements the **Adapter Pattern** to separate data representation from execution logic:

- **Data Models** (`Cell`, `Book`, `NotebookItem`): Pure Pydantic models representing data
- **Adapters** (`UnifiedNotebookItemAdapter`, `CellAdapter`, `BookAdapter`): Provide execution behavior via `IPipelineExecutable`

## Usage

### Unified Adapter (Recommended)

```python
from app.models.adapters import UnifiedNotebookItemAdapter
from app.core.models import PipelineItem, NotebookItem

# For a Cell
cell = NotebookItem(assignee_id="user-123", kind="cell", ...)
adapter = UnifiedNotebookItemAdapter(item=cell, pipeline_context_name="unified_runtime")

# Create pipeline item
pipeline_item = PipelineItem(
    notebook_item_id=cell.id,
    notebook_item_data=cell,
    cell_id=cell.id,
    cell_type_id=cell.notebook_item_type_id,
    assignee_id=cell.assignee_id
)

# Execute (automatically dispatches based on kind)
result = await adapter.execute_in_pipeline(pipeline_item)

# For a Book with DAG mode
book = NotebookItem(
    assignee_id="user-123",
    kind="book",
    execution_mode="dag",
    cells=["cell-1", "cell-2"]
)
adapter = UnifiedNotebookItemAdapter(item=book, pipeline_context_name="unified_runtime")
result = await adapter.execute_in_pipeline(pipeline_item)
```

### Legacy Cell Execution (Backward Compatible)

```python
from app.models.adapters import CellAdapter
from app.core.models import PipelineItem

# Wrap a cell with an adapter (automatically sets kind='cell')
cell_adapter = CellAdapter(cell)

# Create a pipeline item for execution
pipeline_item = PipelineItem(
    notebook_item_id=cell.id,
    notebook_item_data=cell,
    cell_id=cell.id,
    cell_type_id=cell.notebook_item_type_id,
    assignee_id=cell.assignee_id
)

# Execute the cell (delegates to UnifiedNotebookItemAdapter)
result = await cell_adapter.execute_in_pipeline(pipeline_item)
```

### Legacy Book Execution (Backward Compatible)

```python
from app.models.adapters import BookAdapter
from app.core.models import PipelineItem

# Wrap a book with an adapter (automatically sets kind='book', execution_mode='dag')
book_adapter = BookAdapter(book)

# Create a pipeline item for execution
pipeline_item = PipelineItem(
    notebook_item_id=book.id,
    notebook_item_data=book,
    cell_id=book.id,
    cell_type_id="book-type",
    assignee_id=book.assignee_id
)

# Execute the book (delegates to UnifiedNotebookItemAdapter)
result = await book_adapter.execute_in_pipeline(pipeline_item)
```

## Classes

### UnifiedNotebookItemAdapter ⭐ NEW

**The main unified adapter for both cells and books.**

**Responsibilities:**
- Dispatch execution based on `kind` field (cell vs book)
- Execute cells via `_run_cell()` method
- Execute books via `_run_book()` with dual-mode support
- Implement hierarchical tracing with `executed_by` field
- Manage fragments and status propagation
- Handle AWAITING_REVIEW pause behavior

**Key Methods:**
- `execute_in_pipeline()`: Main unified execution entry point
- `_dispatch_by_kind()`: Routes to cell or book execution
- `_run_cell()`: Execute cell-specific logic
- `_run_book()`: Execute book with mode dispatch (DAG/Script/Hybrid)
- `_run_book_dag_mode()`: Parallel execution mode
- `_run_book_script_mode()`: Sequential/imperative execution
- `_run_book_hybrid_mode()`: Mixed parallel and imperative
- `_execute_cells_sequentially()`: Sequential cell execution with tracing
- `_inject_executed_by()`: Inject parent book ID into child fragments

**Architecture Reference:**
- `docs/issues/discovery-planning-system-epic/TO_BE_VISION.md` (Section 4.1: Unified Runtime)
- `docs/issues/discovery-planning-system-epic/ACTION_PLAN.md` (Unified Notebook Runtime)

### NotebookItemAdapter (Base Class)

Base adapter implementing the `IPipelineExecutable` interface.

**Responsibilities:**
- Wrap a `NotebookItem` via composition
- Provide dynamic workflow loading
- Support workflow path resolution with priority (instance refs > type refs)
- Persist execution records to database
- Handle execution errors

**Key Methods:**
- `execute_in_pipeline()`: Main execution orchestration (overridden by UnifiedNotebookItemAdapter)
- `_persist_execution_record()`: Save execution results to database
- `get_references()`: Access notebook item refs
- `get_notebook_item()`: Access wrapped item

### CellAdapter (Legacy Wrapper)

**Thin wrapper around UnifiedNotebookItemAdapter for backward compatibility.**

**Migration Note:** New code should use `UnifiedNotebookItemAdapter` directly. This wrapper exists to maintain backward compatibility with existing code.

**Automatic Setup:**
- Sets `kind='cell'` on the wrapped item
- Sets default `pipeline_context_name='cell_execution'`

### BookAdapter (Legacy Wrapper)

**Thin wrapper around UnifiedNotebookItemAdapter for backward compatibility.**

**Migration Note:** New code should use `UnifiedNotebookItemAdapter` directly. This wrapper exists to maintain backward compatibility with existing code.

**Automatic Setup:**
- Sets `kind='book'` on the wrapped item
- Sets default `execution_mode='dag'` if not specified
- Sets default `pipeline_context_name='book_orchestration'`

## Dual-Mode Book Execution

Books can declare their execution strategy via the `execution_mode` field:

### Execution Modes

**1. DAG Mode (Declarative, Parallel)**
```python
book = NotebookItem(
    kind="book",
    execution_mode="dag",
    cells=["cell-1", "cell-2", "cell-3"]
)
# Executes cells in parallel where possible, respects dependencies
```

**2. Script Mode (Imperative, Sequential)**
```python
book = NotebookItem(
    kind="book",
    execution_mode="script",
    cells=["cell-1", "cell-2", "cell-3"]
)
# Executes cells sequentially in order, allows complex logic
```

**3. Hybrid Mode (Mixed)**
```python
book = NotebookItem(
    kind="book",
    execution_mode="hybrid",
    cells=["cell-1", "cell-2", "cell-3"]
)
# Combines parallel and sequential execution for maximum flexibility
```

## Hierarchical Tracing

The unified adapter implements hierarchical tracing to track which NotebookItem executed which steps:

```python
# Parent book execution
book = NotebookItem(id="book-123", kind="book", cells=["cell-1"])

# Child cell execution
# The adapter automatically injects executed_by="book-123" into child fragments
result = await adapter._execute_cells_sequentially(pipeline_item)

# Now child fragments have executed_by field set:
# fragment.executed_by == "book-123"
```

This enables:
- ✅ Complete execution trace from books to cells
- ✅ Debugging and auditing of execution flows
- ✅ Understanding which book triggered which cells

## AWAITING_REVIEW Pause Behavior

When a cell's status is set to `AWAITING_REVIEW`, book execution pauses:

```python
# Cell 1 completes successfully
# Cell 2 requires review -> status = "AWAITING_REVIEW"
# Book execution pauses, Cell 3 is not executed
# Book status becomes "AWAITING_REVIEW"

# After human approval, execution can resume
```

## Workflow Loading

Adapters support dynamic workflow loading with flexible path resolution:

### Priority Order

1. **Instance refs** (if `allow_instance_override_refs = true`)
2. **Type default_refs** (from `NotebookItemType`)
3. **Fallback**: Instance refs (if no type found)

### Supported Workflow Formats

- **Module path**: `"app.workflows.ingestion_graph"`
- **File path**: `"/path/to/workflow.py"` (fallback)

### Execution Functions

Workflows must expose one of:
- `execute_workflow(workflow_path, pipeline_item, notebook_item_data)`
- `execute(pipeline_item)`

## Execution Record Persistence

After execution, adapters persist execution records to the database:

1. Create `ExecutionRecord` DTO from `PipelineItem`
2. Convert to dict with type marker
3. Append to `notebook_item.fragments`
4. Update database (collection: `cells` or `books`)

## Error Handling

Adapters handle errors gracefully:

- Catch execution exceptions
- Set error on `PipelineItem`
- Add error fragment to notebook item
- Persist execution record (even on failure)
- Re-raise exception for caller to handle

## Testing

Tests are located in:
- `tests/unit/adapters/test_notebook_item_adapter.py` ⭐ **NEW** (Comprehensive unified adapter tests)
- `tests/unit/backend/models/test_adapters.py` (Legacy adapter tests)

Run tests with:
```bash
# New unified adapter tests (17 tests, 90%+ coverage)
poetry run pytest tests/unit/adapters/test_notebook_item_adapter.py -v

# Legacy adapter tests
poetry run pytest tests/unit/backend/models/test_adapters.py -v
```

### Test Coverage

The unified adapter test suite covers:
- ✅ Dispatch by kind (cell vs book)
- ✅ Cell execution through unified adapter
- ✅ Book execution with dual-mode dispatch (DAG/Script/Hybrid)
- ✅ Hierarchical tracing (executed_by field injection)
- ✅ Fragment management and status propagation
- ✅ AWAITING_REVIEW pause behavior
- ✅ Backward compatibility with legacy adapters
- ✅ Error handling and recovery

## Migration Guide

### From Legacy Adapters to Unified Adapter

**Before:**
```python
from app.models.adapters import CellAdapter, BookAdapter

# Cell execution
cell_adapter = CellAdapter(cell)
result = await cell_adapter.execute_in_pipeline(pipeline_item)

# Book execution
book_adapter = BookAdapter(book)
result = await book_adapter.execute_in_pipeline(pipeline_item)
```

**After:**
```python
from app.models.adapters import UnifiedNotebookItemAdapter

# Cell execution
adapter = UnifiedNotebookItemAdapter(item=cell, pipeline_context_name="unified_runtime")
result = await adapter.execute_in_pipeline(pipeline_item)

# Book execution
adapter = UnifiedNotebookItemAdapter(item=book, pipeline_context_name="unified_runtime")
result = await adapter.execute_in_pipeline(pipeline_item)
```

**Note:** Legacy adapters still work! They delegate to `UnifiedNotebookItemAdapter` internally.

## Backward Compatibility

The package maintains the same public API:

```python
# Old imports (still work, now as thin wrappers)
from app.models.adapters import CellAdapter, BookAdapter

# New unified adapter
from app.models.adapters import UnifiedNotebookItemAdapter

# All imports
from app.models.adapters import (
    NotebookItemAdapter,  # Base class
    UnifiedNotebookItemAdapter,  # Unified implementation
    CellAdapter,  # Legacy wrapper
    BookAdapter,  # Legacy wrapper
)
```

## References

- **Issue 0.3**: `docs/issues/discovery-planning-system-epic/0.3-foundation-notebook-item-adapter.md`
- **TO-BE Vision**: `docs/issues/discovery-planning-system-epic/TO_BE_VISION.md`
- **Action Plan**: `docs/issues/discovery-planning-system-epic/ACTION_PLAN.md`
