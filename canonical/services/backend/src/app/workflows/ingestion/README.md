---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - workflows
  - ingestion
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Document Ingestion Workflow Module

This directory contains the modularized LangGraph-based workflow for document ingestion into the ScareVerse RAG system.

## Overview

The ingestion workflow processes documents through multiple stages:
1. **File Resolution**: Download from URL or use local file path
2. **Preprocessing**: Load and preprocess source documents
3. **Chunking**: Split documents into manageable chunks
4. **Embedding Generation**: Create vector embeddings using AI models
5. **Storage**: Store embeddings in ChromaDB vector database

## Module Structure

### Files and Responsibilities

```
ingestion/
├── __init__.py (61 lines)
│   └── Public API exports and backward compatibility
│
├── ingestion_orchestrator.py (322 lines)
│   └── Main execution entry point with PipelineItem lifecycle support
│   └── Handles operation types: new, update, delete
│
├── ingestion_graph_builder.py (146 lines)
│   └── LangGraph construction and configuration
│   └── Node assembly and edge routing
│
├── ingestion_node_types.py (333 lines)
│   └── Individual workflow node implementations
│   └── State definition (IngestionState TypedDict)
│   └── Node functions: initialize, resolve, preprocess, embed, finalize
│
└── ingestion_workflow_utils.py (136 lines)
    └── Shared utility functions
    └── URL detection and file downloading
    └── External script execution
```

### Backward Compatibility

The original `ingestion_graph.py` (72 lines) is now a backward compatibility shim that re-exports the modular API. Existing code will continue to work without changes:

```python
# Old imports still work
from app.workflows import ingestion_graph
result = ingestion_graph.execute(pipeline_item)

# New recommended imports
from app.workflows.ingestion import execute
result = execute(pipeline_item)
```

## Usage

### Basic Execution

```python
from app.workflows.ingestion import execute
from app.core.models import PipelineItem

# Create pipeline item with document data
item = PipelineItem(
    cell_id="cell-123",
    data={
        "file_path": "https://example.com/document.pdf",
        "file_type": "pdf",
        "document_id": "doc-456",
        "operation_type": "new"  # or "update" or "delete"
    },
    agent_data={
        "model_ia_model_id_ref": "mistral"
    }
)

# Execute workflow
result = execute(item)

# Check result
if result.error:
    print(f"Error: {result.error}")
else:
    print(f"Status: {result.status}")
    print(f"Fragments: {result.fragments}")
```

### Operation Types

1. **New Ingestion** (`operation_type="new"`):
   - Full ingestion pipeline
   - Downloads file (if URL) → Preprocess → Chunk → Embed → Store

2. **Update Ingestion** (`operation_type="update"`):
   - Delete old embeddings first
   - Then perform full ingestion (same as "new")

3. **Delete** (`operation_type="delete"`):
   - Only delete embeddings for the document
   - No preprocessing or embedding generation

### Dynamic Graph Loading

For orchestrator-based execution:

```python
from app.workflows.ingestion import get_workflow_graph

# Get compiled LangGraph
graph = get_workflow_graph()

# Execute with state
initial_state = {
    "cell_id": "cell-123",
    "cell_data": {...},
    "agent_data": {...},
    # ... other state fields
}

result = graph.invoke(initial_state)
```

## Configuration

### Environment Variables

The workflow uses configuration from `app.config`:
- `BASE_DIR`: Base directory for resolving script paths
- Embedding models configured via agent_data

### Script Dependencies

The workflow may call external scripts via subprocess fallback:
- `scripts/ingestion/preprocess_and_chunk.py`: Document preprocessing
- `scripts/ingestion/generate_embeddings_and_store.py`: Embedding generation

Preferably, these scripts expose an `execute(item: PipelineItem)` function for direct importlib-based calling.

## State Management

The workflow uses `IngestionState` TypedDict for graph state:

```python
class IngestionState(TypedDict):
    # Cell context
    cell_id: str
    cell_data: Dict[str, Any]
    agent_data: Dict[str, Any]
    
    # Workflow data
    file_path: str
    file_type: str
    document_id: str
    local_file_path: Optional[str]
    
    # Step outputs
    chunks_path: Optional[str]
    embedding_status: Optional[str]
    
    # Execution tracking
    fragments: List[Dict[str, Any]]
    context: Dict[str, Any]
    error: Optional[str]
    completed: bool
```

## Testing

Run unit tests for the ingestion workflow:

```bash
# Run all ingestion tests
pytest tests/unit/backend/test_document_ingestion.py -v

# Run specific test
pytest tests/unit/backend/test_document_ingestion.py::TestIngestionWorkflow -v
```

## Logging

The workflow uses Python's logging module:

```python
import logging
logger = logging.getLogger(__name__)
```

All modules log to `backend.app.workflows.ingestion.*` namespace.

## Error Handling

Errors are captured and stored in the PipelineItem:

```python
if result.error:
    print(f"Workflow failed: {result.error}")
    # Error details also available in fragments
    for fragment in result.fragments:
        if fragment.get("tipo") == "execucao" and "error" in fragment.get("conteudo", "").lower():
            print(f"Error fragment: {fragment}")
```

## Extension Points

### Adding New Nodes

1. Define node function in `ingestion_node_types.py`:
```python
def my_new_node(state: IngestionState) -> IngestionState:
    logger.info("Executing new node")
    # Node logic here
    state["context"]["steps_completed"].append("my_new_node")
    return state
```

2. Add node to graph in `ingestion_graph_builder.py`:
```python
workflow.add_node("my_node", my_new_node)
workflow.add_edge("previous_node", "my_node")
```

### Adding Utilities

Add shared utility functions to `ingestion_workflow_utils.py`:
```python
def my_utility_function(param: str) -> str:
    """Utility function description."""
    # Implementation
    return result
```

## Migration Guide

### For Developers

If your code imports from `ingestion_graph.py`, consider updating to the new structure:

**Before:**
```python
from app.workflows.ingestion_graph import execute, get_workflow_graph
```

**After:**
```python
from app.workflows.ingestion import execute, get_workflow_graph
```

The old imports still work via the compatibility shim, but the new imports are preferred.

### For Orchestrator

The orchestrator can continue using the python_refs as before:
```
python_refs: ["backend/app/workflows/ingestion_graph.py"]
```

The shim will redirect to the new modular structure transparently.

## Compliance

This modularization addresses **Rule 1.1 (File Size Limit)** from RULESET.md:
- ✅ Original file: 866 lines → **VIOLATION**
- ✅ Modularized: All files < 500 lines → **COMPLIANT**
  - `__init__.py`: 61 lines
  - `ingestion_orchestrator.py`: 322 lines
  - `ingestion_graph_builder.py`: 146 lines
  - `ingestion_node_types.py`: 333 lines
  - `ingestion_workflow_utils.py`: 136 lines
  - `ingestion_graph.py` (shim): 72 lines

## References

- [RULESET.md](../../../../RULESET.md) - Project rules and standards
- [GAP_RESOLUTION_GUIDE.md](../../../../docs/GAP_RESOLUTION_GUIDE.md) - Gap remediation guidelines
- [copilot_instructions.md](../../../../copilot_instructions.md) - General development guidelines
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph) - LangGraph framework

## Support

For questions or issues:
1. Check this README
2. Review inline documentation in source files
3. Open an issue with tag `workflow-ingestion`
