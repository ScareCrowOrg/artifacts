---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - rag
  - retrieval
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# RAG Module

## Overview

This module provides Advanced Retrieval Augmented Generation (RAG) functionality with ensemble retrieval across multiple collections and embedding models.

**Modularization Date**: 2025-11-21  
**Previous Structure**: Single file (`rag_service.py`, 630 lines)  
**Current Structure**: Modularized into subdirectory with 4 modules

## Module Structure

```
rag/
├── __init__.py               # Public API exports (backward compatible)
├── config.py                 # RAG configuration and constants (~50 lines)
├── embeddings.py             # Embedding function management (~80 lines)
├── retriever_manager.py      # Retriever creation and ensemble logic (~230 lines)
├── rag_service.py            # Main RAGService class (~270 lines)
└── README.md                 # This file
```

## Files

### `__init__.py`

**Purpose**: Public API exports maintaining backward compatibility.

**Exports**:
- `RAGService` - Main service class
- `get_rag_service` - Factory function
- `get_embedding_function_for_model_id` - Embedding function utility
- Configuration constants

**Example**:
```python
# All imports work as before (backward compatible)
from backend.app.services.rag_service import RAGService, get_rag_service
```

### `config.py`

**Purpose**: RAG-specific configuration and constants.

**Contents**:
- `DEFAULT_RAG_K` - Default number of documents to retrieve (5)
- `OPENAI_DEFAULT_EMBEDDING_MODEL` - Default OpenAI embedding model
- `COLLECTION_TO_EMBEDDING_MODEL` - Mapping of collections to embedding models
- `AVAILABLE_COLLECTION_NAMES` - List of valid collection names

**Example**:
```python
from backend.app.services.rag.config import COLLECTION_TO_EMBEDDING_MODEL

# Get embedding model for a collection
model = COLLECTION_TO_EMBEDDING_MODEL['scareverse_docs']  # 'mistral'
```

### `embeddings.py`

**Purpose**: Embedding function management for Ollama and OpenAI models.

**Functions**:
- `get_embedding_function_for_model_id(model_id, api_key)` - Create embedding function

**Supported Models**:
- **Ollama (local)**: mistral, phi, deepseek-coder
- **OpenAI (API)**: text-embedding-ada-002, text-embedding-3-small, text-embedding-3-large

**Example**:
```python
from backend.app.services.rag.embeddings import get_embedding_function_for_model_id

# Ollama model
embeddings = get_embedding_function_for_model_id('mistral')

# OpenAI model
embeddings = get_embedding_function_for_model_id(
    'text-embedding-3-small',
    api_key='sk-...'
)
```

### `retriever_manager.py`

**Purpose**: Manages vector store retrievers and ensemble retrieval.

**Classes**:
- `RetrieverManager` - Manages retriever creation and lifecycle

**Key Methods**:
- `get_retriever_for_collection(collection_name, k)` - Get retriever for single collection
- `get_ensemble_retriever(k, selected_collections)` - Create ensemble retriever

**Features**:
- Dynamic embedding model selection per collection
- Collection validation and filtering
- No caching (always fresh retrievers)
- Detailed logging

**Example**:
```python
from backend.app.services.rag.retriever_manager import RetrieverManager

manager = RetrieverManager()

# Single collection
retriever = manager.get_retriever_for_collection('scareverse_docs', k=5)

# Ensemble retrieval
ensemble = manager.get_ensemble_retriever(
    k=5,
    selected_collections=['scareverse_docs', 'scareverse_code']
)
```

### `rag_service.py`

**Purpose**: Main RAG service providing high-level RAG operations.

**Classes**:
- `RAGService` - Main service class with ensemble retrieval

**Key Methods**:
- `get_context(user_message, ...)` - Retrieve RAG context (main entry point)
- `search_similar(query, k, collection_name)` - Similarity search
- `ensure_vectorstore_exists()` - Check vector store availability
- `debug_vectorstore()` - Debug utility

**Functions**:
- `get_rag_service(...)` - Factory function to create service instances

**Example**:
```python
from backend.app.services.rag_service import get_rag_service

# Create service
rag = get_rag_service(
    collection_names=['scareverse_docs', 'scareverse_code'],
    ensemble_weights=[0.6, 0.4]
)

# Retrieve context
message, docs, context = await rag.get_context(
    user_message="Explain API architecture",
    selected_collections=["scareverse_docs"],
    enable_query_expansion=True,
    enable_postprocessing=True
)
```

## Usage

### Basic Usage (unchanged from original)

```python
from backend.app.services.rag_service import get_rag_service

# Create service
rag = get_rag_service()

# Get context
message, docs, context = await rag.get_context(
    user_message="How do I create a cell?",
    selected_collections=["scareverse_docs"]
)
```

### Advanced Usage

```python
from backend.app.services.rag_service import get_rag_service

# Custom collections and weights
rag = get_rag_service(
    collection_names=['scareverse_docs', 'scareverse_code'],
    ensemble_weights=[0.7, 0.3]
)

# Full-featured context retrieval
message, docs, context = await rag.get_context(
    user_message="Implement file upload",
    session_id="dev_session_1",
    k=5,
    selected_collections=["scareverse_code"],
    enable_query_expansion=True,
    enable_postprocessing=True
)
```

## Backward Compatibility

✅ **All existing imports continue to work**:
```python
# These all work as before
from backend.app.services.rag_service import RAGService, get_rag_service
from app.services.rag_service import RAGService, get_rag_service
```

✅ **All public APIs unchanged**:
- `RAGService.__init__(...)`
- `RAGService.get_context(...)`
- `RAGService.search_similar(...)`
- `get_rag_service(...)`
- `get_embedding_function_for_model_id(...)`

## Benefits of Modularization

1. **Compliance**: Each file now under 500-line limit (Rule 1.1)
2. **Separation of Concerns**: Clear responsibility boundaries
3. **Maintainability**: Easier to test and modify individual components
4. **Reusability**: Embedding and retriever logic can be reused independently
5. **Readability**: Smaller, focused modules are easier to understand

## Configuration

All configuration is centralized in `backend/app/config.py`:

```python
# Vector store
RAG_VECTORSTORE_PATH = BASE_DIR / "chroma_db"

# Ollama
OLLAMA_EMBEDDING_MODEL = "mistral"
OLLAMA_BASE_URL = "http://localhost:11434"

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Post-processing
RAG_POSTPROCESS_LLM_ENABLED = False
RAG_POSTPROCESS_LLM_MODEL = "phi3"
```

## Testing

Tests remain unchanged and continue to work with the modularized structure:

```bash
# Unit tests
pytest tests/unit/backend/test_rag_service.py -v
pytest tests/unit/backend/test_rag_collection_selection.py -v

# Integration tests
pytest tests/integration/backend/test_orchestrator_rag.py -v

# With coverage
pytest tests/unit/backend/test_rag_service.py --cov=backend/app/services/rag --cov-report=term-missing
```

## Collection Mapping

```python
COLLECTION_TO_EMBEDDING_MODEL = {
    'scareverse_docs': 'mistral',       # Documentation
    'scareverse_code': 'deepseek-coder', # Source code
    'scareverse_config': 'deepseek-coder', # Config files
    'scareverse_md': 'mistral',         # Markdown
    'scareverse_json': 'deepseek-coder', # JSON
    'scareverse_yml': 'deepseek-coder',  # YAML
}
```

## Migration Notes

**For Developers**:
- No code changes required - all imports continue to work
- Internal structure is cleaner and more maintainable
- Tests pass without modification

**For Future Development**:
- Add new embedding models in `embeddings.py`
- Extend retriever logic in `retriever_manager.py`
- Add service features in `rag_service.py`
- Update configuration in `config.py`

## References

- [Parent Services README](../README.md) - Overview of all services
- [RULESET.md](../../../../RULESET.md) - Project coding standards (Rule 1.1: File size limit)
- [RAG_INTEGRATION_SUMMARY.md](../../../../RAG_INTEGRATION_SUMMARY.md) - RAG implementation details

---

**Last Updated**: 2025-11-21  
**Status**: ✅ Compliant with Rule 1.1 (all files < 500 lines)  
**Backward Compatibility**: ✅ Full (all existing code works unchanged)
