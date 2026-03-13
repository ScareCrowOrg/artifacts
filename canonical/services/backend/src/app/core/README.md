---
processed: true
processed_date: 2025-12-08
themes:
  - backend
  - core
  - architecture
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Core Models and Utilities

This directory contains core data models and utilities for ScareVerse pipeline orchestration.

## Purpose

The `core` module provides foundational models used throughout the orchestration system, focusing on in-process workflow execution with full traceability.

## Files

- **`__init__.py`**: Module initialization, exports main classes
- **`models.py`**: Core Pydantic models for pipeline execution
  - `Fragmento`: Execution/memory fragment for traceability
  - `PipelineItem`: Central artifact for workflow execution

## Models Overview


### Fragmento

Represents a discrete unit of work or context during pipeline execution. Acts as a digital "notebook entry" capable of recording any type of information without data loss or rigid validation.

**Nota:**
Em outros módulos, como células, o campo `fragmentos` pode ser representado diretamente como lista de strings livres, para máxima flexibilidade e simplicidade. O modelo Fragmento segue disponível para cenários que exigem estruturação adicional.

Each fragment has:
- `id`: Unique identifier (auto-generated)
- `tipo`: Type (any string for categorization: "narrative", "memory", "execucao", "log", "error", "debug", custom types, etc.)
- `conteudo`: Main content (can be text, JSON object, list, number, or any serializable data)
- `resultado`: Optional result of an operation (can be any type)
- `timestamp`: Creation time (auto-generated)
- `metadata`: Additional context (dictionary)

**Usage:**
```python
from app.core import Fragmento

# Text fragment
fragment1 = Fragmento(
    tipo="execucao",
    conteudo="Document chunked successfully"
)

# JSON object fragment
fragment2 = Fragmento(
    tipo="narrative",
    conteudo={"story": "Processing started", "chapter": 1},
    resultado={"status": "success"}
)

# List fragment
fragment3 = Fragmento(
    tipo="log",
    conteudo=[1, 2, 3, "items processed"]
)

# Custom type with metadata
fragment4 = Fragmento(
    tipo="my-custom-event",
    conteudo={"event": "data", "nested": {"values": [1, 2, 3]}},
    metadata={"source": "agent-1", "priority": "high"}
)
```

### PipelineItem

Central execution artifact that encapsulates:
- Cell context and identifiers
- Input/output data dictionary
- Execution fragments for traceability
- Status tracking
- Error handling

**Usage:**
```python
from app.core import PipelineItem

item = PipelineItem(
    cell_id="cell-123",
    cell_type_id="ingestion-issue",
    data={"file_path": "/path/to/doc.md"}
)

# Add execution fragment with text
item.add_fragment(
    tipo="execucao",
    conteudo="Processing started"
)

# Add fragment with JSON object
item.add_fragment(
    tipo="narrative",
    conteudo={"story": "Chapter 1", "status": "in-progress"}
)

# Add fragment with result
item.add_fragment(
    tipo="metric",
    conteudo={"metric_name": "processing_time"},
    resultado={"value": 42.5, "unit": "seconds"}
)

# Update status
item.update_status("running")
    conteudo="Processing started"
)

# Update status
item.update_status("running")

# Merge new data
item.merge_data({"chunks_path": "/tmp/chunks.json"})
```

## Integration Points

- **Orchestrator**: Converts Celula to PipelineItem, manages execution lifecycle
- **Workflows**: Accept and return PipelineItem instances
- **Scripts**: Expose `execute(item: PipelineItem) -> PipelineItem` functions
- **Redis**: Fragments are published to Redis channels for real-time streaming
- **Event Bus**: State changes trigger events for UI updates

## Design Principles

1. **Type Safety**: Pydantic models provide validation and serialization
2. **Traceability**: Fragments capture every step of execution
3. **Flexibility**: Generic data dictionary accommodates any workflow
4. **In-Process**: Eliminates subprocess overhead for better performance
5. **Streamable**: Models serialize cleanly for Redis/SSE streaming

## Configuration

No specific configuration required. Models use standard Pydantic defaults.

## Testing

Unit tests for core models are located in `tests/unit/backend/test_core_models.py`.

See also:
- `backend/app/orchestrator.py` - Main orchestration logic
- `backend/app/workflows/` - Workflow definitions
- `scripts/ingestion/` - Auxiliary processing scripts
