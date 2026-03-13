---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - workflows
  - processing
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Workflows Directory

This directory contains custom LangGraph workflow definitions for cell type execution.

## Index

### Files
- [ingestion/](./ingestion/) - Document ingestion workflow with lifecycle management
- [chunking_strategies.py](./chunking_strategies.py) - Intelligent chunking for Markdown, Python, and config files
- [vue_chunking_strategies.py](./vue_chunking_strategies.py) - Intelligent chunking for Vue.js ecosystem files
- [preprocess_and_chunk.py](./preprocess_and_chunk.py) - Main preprocessing and chunking dispatcher

### Subdirectories
- [ingestion/](./ingestion/) - RAG document ingestion workflow graphs

## Overview

Custom workflow graphs provide a more flexible and programmatic alternative to YAML-based workflows. They allow for complex logic, dynamic state management, and better integration with Python tooling.

## How It Works

### Priority Order for Workflow Execution

The orchestrator follows this priority order when executing cells:

1. **Custom Graph Files** (`*graph.py`) - Referenced in `python_refs` of the cell type
2. **YAML Workflow Files** - Referenced in `yaml_refs` of the cell type  
3. **Inline YAML Workflows** - Defined in `workflows` field of the cell type

### Creating a Custom Graph

A custom graph file must:

1. Define a state structure using `TypedDict`
2. Implement workflow nodes as functions
3. Build a `StateGraph` with nodes and edges
4. Provide a `get_workflow_graph()` function that returns the compiled graph

**Example:**

```python
from typing import TypedDict
from langgraph.graph import StateGraph, END

class MyWorkflowState(TypedDict):
    cell_id: str
    cell_data: dict
    agent_data: dict
    # ... other fields

def initialize(state: MyWorkflowState) -> MyWorkflowState:
    # Initialize workflow
    return state

def process(state: MyWorkflowState) -> MyWorkflowState:
    # Process logic
    return state

def build_graph() -> StateGraph:
    workflow = StateGraph(MyWorkflowState)
    workflow.add_node("initialize", initialize)
    workflow.add_node("process", process)
    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "process")
    workflow.add_edge("process", END)
    return workflow.compile()

def get_workflow_graph():
    """Entry point for orchestrator."""
    return build_graph()
```

### Important: Use Absolute Imports

⚠️ **Custom graph files are loaded dynamically using `importlib.util.spec_from_file_location()`**, which means they are loaded as standalone modules without package context.

**Always use absolute imports in custom graph files:**

```python
# ✅ CORRECT - Absolute imports
from app.workflows.ingestion import execute, get_workflow_graph
from app.core.models import PipelineItem
from app.config import BASE_DIR

# ❌ WRONG - Relative imports will fail
from .ingestion import execute  # ImportError: attempted relative import with no known parent package
from ..core.models import PipelineItem  # ImportError
```

**Why:** When loaded dynamically, Python doesn't know about the package hierarchy, so relative imports (`from .module import ...`) will fail with `ImportError: attempted relative import with no known parent package`.

**Solution:** All imports must use the full absolute path starting from the project root (e.g., `app.workflows.ingestion`).

### Referencing a Custom Graph

In your cell type JSON, add the graph file to `python_refs`:

```json
{
  "id": "my-cell-type",
  "name": "My Cell Type",
  "python_refs": [
    "backend/app/workflows/my_workflow_graph.py"
  ],
  ...
}
```

## Available Graphs

### `ingestion_graph.py`

**Purpose:** Document ingestion pipeline for RAG system with lifecycle management

**Features:**
- Supports both local file paths and URLs
- Downloads content from URLs automatically
- Preprocesses and chunks documents
- Generates embeddings and stores in ChromaDB
- Tracks execution with fragments and context
- **NEW:** Full document lifecycle management (new, update, delete operations)
- **NEW:** Content-based change detection via SHA256 hashing
- **NEW:** Automatic cleanup of obsolete embeddings on updates

**Lifecycle Operations:**

1. **New Documents** (`operation_type='new'`):
   - Full ingestion pipeline: preprocess → chunk → embed → store
   - Creates initial cell with content hash

2. **Modified Documents** (`operation_type='update'`):
   - Detects changes via content hash comparison
   - Deletes old embeddings from vector store
   - Re-ingests document with full pipeline
   - Marks previous cell as 'obsolete'
   - References previous cell via `previous_cell_id`

3. **Deleted Documents** (`operation_type='delete'`):
   - Removes all embeddings from vector stores
   - Marks previous cell as 'deleted'
   - No re-ingestion performed

**State Structure:**
```python
class IngestionState(TypedDict):
    cell_id: str
    cell_data: Dict[str, Any]
    agent_data: Dict[str, Any]
    file_path: str  # Local path or URL
    file_type: str
    document_id: str
    operation_type: str  # 'new', 'update', or 'delete'
    content_hash: Optional[str]  # SHA256 of content
    previous_cell_id: Optional[str]  # For update/delete ops
    local_file_path: Optional[str]
    chunks_path: Optional[str]
    embedding_status: Optional[str]
    fragments: List[Dict[str, Any]]
    context: Dict[str, Any]
    error: Optional[str]
    completed: bool
```

**Workflow Nodes:**
1. `initialize_ingestion` - Extract data from cell
2. `resolve_file_path` - Download from URL if needed
3. `preprocess_and_chunk` - Process document into chunks
4. `generate_embeddings` - Create and store embeddings
5. `finalize_ingestion` - Mark workflow complete

**Usage:**
Referenced by `ingestion-issue` cell type. Cells with this type will automatically use the custom graph for execution.

## Intelligent Chunking Strategies

### Overview

The RAG ingestion system uses specialized chunking strategies to generate high-quality, semantically coherent chunks optimized for specific embedding models and collections.

### `chunking_strategies.py`

**Supported File Types:**
- **Markdown** (`.md`): Semantic chunking based on headers (H1, H2, H3)
- **Python** (`.py`): AST-based chunking extracting functions, classes, and docstrings
- **Configuration** (`.yaml`, `.json`, `.env`): Structured chunking respecting file format

**Features:**
- Content cleaning and normalization
- Docstring extraction for dual collection ingestion
- Metadata-rich chunks for precise retrieval

### `vue_chunking_strategies.py` ⭐ NEW

**Purpose:** Intelligent chunking for Vue.js ecosystem files to provide high-quality context for the Frontend Agent.

**Supported File Types:**
- **Vue SFC** (`.vue`): Single File Components
- **Composables** (`.js`/`.ts` in `composables/`): Vue composition functions
- **Pinia Stores** (`.js`/`.ts` in `stores/`): State management stores
- **Component Scripts** (`.js`/`.ts` in `components/`): Component logic files

**Features:**

1. **Vue SFC Parsing**
   - Extracts `<template>`, `<script>`, and `<style>` blocks as separate chunks
   - Preserves Tailwind CSS classes in templates for context
   - Detects script language (TypeScript vs JavaScript)
   - Supports `<script setup>` syntax

2. **JavaScript/TypeScript Analysis**
   - Extracts exported functions (composables like `useAuth`, `useChatIA`)
   - Detects Pinia store definitions (`defineStore`)
   - Identifies function patterns and exports
   - Maintains complete function bodies with proper brace matching

3. **JSDoc and Comment Extraction**
   - Extracts JSDoc blocks associated with functions
   - Includes JSDoc in code chunks for context
   - Separately extracts JSDoc for documentation collection
   - Detects standalone documentation comments

4. **Dual Collection Strategy**
   - **Code chunks** → `scareverse_code` collection with `deepseek-coder` embeddings
     - Complete functions with JSDoc
     - Vue template blocks with Tailwind classes
     - Style blocks
   - **Doc chunks** → `scareverse_docs` collection with `mistral` embeddings
     - JSDoc blocks
     - Inline documentation comments
     - Function descriptions

5. **Frontend File Detection**
   - Automatically detects frontend-specific directories:
     - `cockpit-vue/src/composables/`
     - `cockpit-vue/src/stores/`
     - `cockpit-vue/src/components/`
   - Routes frontend JS/TS files to Vue chunking strategy

**Benefits:**
- **Syntactically Complete**: Code chunks maintain proper syntax and structure
- **Context-Rich**: Includes JSDoc, comments, and Tailwind classes
- **LLM-Optimized**: Separate embeddings for code and documentation
- **Frontend Agent Support**: Provides precise, relevant context for Vue.js development tasks

**Example Chunk Types:**
- `vue_template` - HTML template with Tailwind CSS
- `vue_script_js` / `vue_script_ts` - Component script
- `vue_style_css` / `vue_style_scss` - Component styles
- `vue_composable_function` - Exported composable function
- `vue_pinia_store_pinia_store` - Pinia store definition
- `vue_component_script_function` - Component helper function
- `vue_composable_jsdoc` - Composable documentation

**Usage:**
Automatically invoked by `preprocess_and_chunk.py` dispatcher for:
- Files with `.vue` extension
- `.js`/`.ts` files in frontend directories (`composables/`, `stores/`, `components/`)

### `preprocess_and_chunk.py`

**Purpose:** Main dispatcher for intelligent chunking strategies.

**Features:**
- File type detection and routing
- Frontend JavaScript file identification
- Unified interface for all chunking strategies
- Separate output for code and documentation chunks

**Workflow:**
1. Load and preprocess file content
2. Detect file type and location
3. Route to appropriate chunking strategy:
   - Markdown → `chunk_markdown()`
   - Python → `chunk_python_code()`
   - Vue/Frontend JS → `chunk_vue_code()` ⭐ NEW
   - Configuration → `chunk_configuration_file()`
   - Other code → Generic text splitter
   - Documentation → Generic text splitter
4. Generate separate JSON files for code and doc chunks
5. Return paths for downstream embedding generation

**Usage:**
Referenced by `ingestion-issue` cell type. Cells with this type will automatically use the custom graph for execution.


**Input Requirements:**
- `cell_data.file_path`: Local file path or URL (required)
- `cell_data.file_type`: File type (e.g., 'markdown', 'python') (required)
- `cell_data.document_id`: Document identifier (optional, auto-generated if not provided)
- `agent_data.model_ia_model_id_ref`: Embedding model to use (optional, defaults to 'mistral')

**Output:**
- Updates cell `fragmentos` with execution history (agora como lista de strings livres, podendo conter qualquer texto, log ou resultado)
- Updates cell `data` with:
  - `workflow_context`: Execution metadata
  - `chunks_path`: Path to generated chunks
  - `embedding_status`: Status from embedding generation
  - `local_file_path`: Local path if URL was downloaded

## Benefits of Custom Graphs

1. **Flexibility**: Full Python capabilities for complex logic
2. **Modularity**: Reusable nodes and functions
3. **Type Safety**: TypedDict state provides IDE support and validation
4. **Debugging**: Standard Python debugging tools work
5. **Testing**: Unit test individual nodes easily
6. **Extensibility**: Easy to add new nodes and conditional paths
7. **Auditability**: Built-in support for fragments and context tracking

## Fallback Behavior

If a custom graph fails to load or execute, the orchestrator will:
1. Log the error
2. Mark the cell as ERROR state
3. Store error details in the cell

The system will NOT automatically fall back to YAML workflows to maintain predictability.

## Best Practices

1. **State Management**: Keep state structure clean and well-documented
2. **Error Handling**: Add fragments for both success and error cases
3. **Logging**: Use logger extensively for debugging
4. **Idempotency**: Design nodes to be idempotent where possible
5. **Context Updates**: Update `context` dict with step completion status
6. **Fragment Tracking**: Add fragments for major steps and errors
7. **Resource Cleanup**: Handle temporary files appropriately

## Testing and Coverage

### Test Coverage Status

Current test coverage for workflow modules (updated):

| Module | Coverage | Tests | Status |
|--------|----------|-------|--------|
| **`preprocess_and_chunk.py`** | **95%** | 53 tests | ✅ **EXCEEDS 90% TARGET** |
| **`generate_embeddings_and_store.py`** | **75%** | 40 tests | 🟡 In Progress (83% to target) |
| **`vue_chunking_strategies.py`** | **75%** | 13 tests (existing) | 🟡 In Progress (83% to target) |
| **`chunking_strategies.py`** | **65%** | 13 tests (existing) | 🟡 In Progress (72% to target) |
| `generate_code_embeddings_and_store.py` | 0% | 0 tests | 🔴 Needs Tests |
| `generate_doc_embeddings_and_store.py` | 0% | 0 tests | 🔴 Needs Tests |
| `ingestion/*` modules | 0% | 0 tests | 🔴 Needs Tests |
| **Overall** | **41%** | **93 tests** | 🟡 In Progress |

**Target**: 90%+ coverage for all modules (as per RULESET.md Rule 3.1)

### Running Tests

```bash
# All workflow tests (93 tests, <1 second)
cd backend
pytest tests/unit/backend/workflows/ -v

# With coverage report
pytest tests/unit/backend/workflows/ --cov=app/workflows --cov-report=term --cov-report=html

# Specific test file
pytest tests/unit/backend/workflows/test_preprocess_and_chunk.py -v
pytest tests/unit/backend/workflows/test_generate_embeddings_and_store.py -v

# View HTML coverage report
open htmlcov/index.html
```

### Test Structure

```
tests/unit/backend/workflows/
├── conftest.py                                # Shared fixtures and mocks
├── test_preprocess_and_chunk.py              # 53 tests - 95% coverage ✅
└── test_generate_embeddings_and_store.py     # 40 tests - 75% coverage
```

### Test Details

**test_preprocess_and_chunk.py** (53 tests - 95% coverage):
- Document ID generation and UUID format
- File loading (text, markdown, Python, PDF)
- PDF processing with pypdf fallback
- Text preprocessing (line endings, blank lines, whitespace)
- Frontend file detection (Vue composables/stores)
- Intelligent chunking for all file types (MD, Python, Vue, YAML, JSON, etc.)
- Chunk saving (separate files, Unicode support)
- CLI argument parsing (required/optional args)
- PipelineItem execution flow
- Error handling (missing files, invalid formats, Unicode errors)

**test_generate_embeddings_and_store.py** (40 tests - 75% coverage):
- Collection name mapping (docs/code/config)
- Chunk loading from JSON with validation
- Embedding model initialization
- Chunk ID generation (SHA256 for idempotency)
- ChromaDB storage operations
- Duplicate detection and skipping
- Metadata enrichment
- CLI and PipelineItem execution
- Error handling (missing files, invalid JSON, connection errors)

### Mocking Strategy

All external dependencies are mocked for fast, isolated tests:

- **File I/O**: Mocked via pytest's `tmp_path` fixture
- **Ollama API**: Mocked `OllamaEmbeddings` class
- **ChromaDB**: Mocked `Chroma` vector store
- **PDF Reader**: Mocked `PdfReader` for PDF processing
- **Path.exists()**: Mocked for vectorstore path checks

### Test Categories

1. **Unit Tests** (all current tests)
   - Individual function testing
   - Edge case validation
   - Error handling verification
   - Fast execution (<1 second total)

2. **Integration Tests** (planned)
   - End-to-end workflow testing
   - Real file processing (with test fixtures)
   - Multi-step pipeline validation

### Test Performance

- ✅ **93 tests** executed in **< 1 second**
- ✅ Well under the **2-minute target** for unit tests (ARQUITETURA_TESTES.md)
- ✅ All tests pass with proper mocking
- ✅ Fast iteration for TDD workflow

### Adding New Tests

When adding new workflow functions:

1. Write tests achieving 90%+ coverage
2. Use fixtures from `conftest.py`
3. Mock all external dependencies
4. Test both happy path and error cases
5. Keep execution time fast (<10ms per test)

Example test structure:

```python
def test_my_function(mock_dependency, tmp_path):
    """Test description."""
    # Arrange
    input_data = create_test_data()
    
    # Act
    result = my_function(input_data)
    
    # Assert
    assert result is not None
    assert 'expected_field' in result
    mock_dependency.assert_called_once()
```

## Testing Custom Graphs

Test your custom graphs by:

1. **Unit Testing Nodes**: Test individual node functions
2. **Integration Testing**: Test the full graph with mock data
3. **Manual Testing**: Create test cells and execute via orchestrator

Example test structure:
```python
def test_my_workflow_node():
    state = {
        "cell_id": "test-123",
        # ... other fields
    }
    result = my_node_function(state)
    assert result["error"] is None
    assert "expected_field" in result
```

## Migration from YAML Workflows

To migrate a YAML workflow to a custom graph:

1. Create a new `*_graph.py` file in this directory
2. Convert YAML steps to node functions
3. Implement state structure with all needed fields
4. Build graph with nodes and edges matching YAML flow
5. Update cell type `python_refs` to reference new graph
6. Test thoroughly before deploying
7. Keep YAML workflow as backup during transition

## Troubleshooting

**Graph file not found:**
- Check that path in `python_refs` is relative to BASE_DIR
- Verify file exists and has correct permissions

**No get_workflow_graph function:**
- Ensure file defines `get_workflow_graph()` function
- Check for typos in function name

**Import errors in graph file:**
- Verify all dependencies are installed
- Check that imports are correct
- Look for circular dependencies

**State mismatch errors:**
- Ensure all nodes return state with correct structure
- Check TypedDict definition matches actual usage
- Verify conditional edge functions return correct node names

## Future Enhancements

Planned improvements:
- Graph versioning support
- Hot-reloading of graphs during development
- Graph validation utilities
- Performance monitoring per node
- Visual graph editor/debugger
- Graph composition (reusable sub-graphs)
