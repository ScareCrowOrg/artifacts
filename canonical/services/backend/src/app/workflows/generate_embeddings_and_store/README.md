---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - workflows
  - embeddings
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Generate Embeddings and Store Module

This module generates embeddings for preprocessed document chunks and stores them in ChromaDB vector stores. It's designed for the document ingestion pipeline.

## Module Structure

```
generate_embeddings_and_store/
├── __init__.py                       # Public API exports
├── collection_mapper.py              # ChromaDB collection mapping (76 lines)
├── embeddings_chunk_loader.py        # JSON chunk loading (61 lines)
├── embeddings_model_manager.py       # Embedding model initialization (64 lines)
├── embeddings_chromadb_store.py      # Storage and deletion operations (259 lines)
├── embeddings_pipeline.py            # PipelineItem integration (147 lines)
├── embeddings_cli.py                 # Command-line interface (142 lines)
└── README.md                         # This file
```

## Usage

### As Python Module (PipelineItem)

```python
from app.workflows.generate_embeddings_and_store import execute
from app.core.models import PipelineItem

item = PipelineItem(data={
    "chunks_json_path": "/path/to/chunks.json",
    "embedding_model_id": "mistral",
    "file_type": "markdown",
    "document_id": "doc123"
})

result_item = execute(item)
```

### As CLI Tool

```bash
python -m app.workflows.generate_embeddings_and_store.embeddings_cli \
    --chunks-json-path /path/to/chunks.json \
    --embedding-model-id mistral \
    --file-type markdown \
    --document-id doc123
```

### Individual Functions

```python
from app.workflows.generate_embeddings_and_store import (
    load_chunks_from_json,
    initialize_embedding_model,
    store_chunks_in_chromadb,
    get_collection_name_from_file_type
)

# Load chunks
chunks = load_chunks_from_json("chunks.json")

# Initialize embedding model
embeddings = initialize_embedding_model("mistral")

# Determine collection
collection = get_collection_name_from_file_type("python")  # Returns 'scareverse_code'

# Store chunks
result = store_chunks_in_chromadb(
    chunks=chunks,
    embeddings=embeddings,
    collection_name=collection,
    document_id="doc123",
    file_type="python"
)
```

## Module Responsibilities

### collection_mapper.py
- Maps file types to ChromaDB collection names
- Determines appropriate embedding models for collections
- Supports: docs, code, and config collections

### embeddings_chunk_loader.py
- Loads preprocessed chunks from JSON files
- Validates chunk format (text + metadata)
- Handles missing metadata gracefully

### embeddings_model_manager.py
- Initializes Ollama embedding models
- Generates unique chunk IDs for idempotency
- Supports multiple embedding models (mistral, deepseek-coder, etc.)

### embeddings_chromadb_store.py
- Stores chunks in ChromaDB with deduplication
- Deletes embeddings by document ID
- Manages vector store persistence
- Provides idempotent ingestion

### embeddings_pipeline.py
- PipelineItem-compatible execution interface
- Validates input parameters
- Orchestrates chunk loading, embedding, and storage
- Updates PipelineItem with results

### embeddings_cli.py
- Command-line argument parsing
- Standalone CLI execution
- Error handling and status reporting

## Collection Strategy

The module uses three main collections:

- **scareverse_docs**: Documentation and text files (markdown, PDF, txt)
- **scareverse_code**: Source code files (Python, JS, etc.)
- **scareverse_config**: Configuration files (JSON, YAML, etc.)

## Idempotency

Chunks are assigned unique IDs based on content + source. Re-ingesting the same chunks is safe and efficient - duplicates are automatically skipped.

## Configuration

Required environment variables (from `app.config`):
- `OLLAMA_BASE_URL`: Ollama API endpoint
- `VECTORSTORE_PATH`: ChromaDB storage directory

## Error Handling

- `FileNotFoundError`: Chunks JSON file not found
- `ValueError`: Invalid JSON format or missing required fields
- `ImportError`: Missing LangChain dependencies

## Backward Compatibility

The `__init__.py` exports all public functions, maintaining the same API as the original monolithic file:

```python
# Old import (still works)
from app.workflows.generate_embeddings_and_store import execute

# New imports (also available)
from app.workflows.generate_embeddings_and_store import (
    load_chunks_from_json,
    store_chunks_in_chromadb
)
```

## Testing

Tests are located in `tests/unit/backend/workflows/test_embeddings_workflow.py`.

Run tests with:
```bash
pytest tests/unit/backend/workflows/test_embeddings_workflow.py -v
```

## Dependencies

- `langchain-chroma`: ChromaDB integration
- `langchain-community`: Ollama embeddings
- `langchain-core`: Document models
