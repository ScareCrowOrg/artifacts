---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - workflows
  - models
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Workflow Models

This directory contains Pydantic data models for workflow data structures.

## Overview

These models provide type safety and runtime validation for data structures used throughout the ingestion pipeline and other workflows.

## Models

### Chunk Models (`chunk_models.py`)

Defines the canonical chunk structure used in the ingestion pipeline:

- **`Chunk`**: Main chunk model with `text` and `metadata` fields
- **`ChunkMetadata`**: Metadata model with document IDs, file types, embedding configuration
- **`ChunkType`**: Enum for different chunk content types
- **`TargetCollection`**: Enum for ChromaDB target collections

**Key Features**:
- Automatic validation of required fields
- Type safety with Pydantic v2
- Auto-population of `char_count` if not provided
- Support for additional metadata fields from specialized chunkers
- JSON serialization/deserialization helpers

**Usage Example**:
```python
from app.workflows.models import Chunk, ChunkMetadata

# Create a chunk
chunk = Chunk(
    text="This is the chunk content",
    metadata=ChunkMetadata(
        chunk_id="0",
        document_id="doc123",
        source="/path/to/file.py",
        file_type="python",
        chunk_index=0,
        embedding_model_id="deepseek-coder",
        target_collection="scareverse_code"
    )
)

# Convert to dict for JSON serialization
chunk_dict = chunk.to_dict()

# Load from dict with validation
loaded_chunk = Chunk.from_dict(chunk_dict)
```

## Related Documentation

- [Issue #1006 Technical Analysis](/home/runner/_work/ScareVerseLab/ScareVerseLab/docs/issues/1006/TECHNICAL_ANALYSIS.md) - Original bug that motivated this implementation
- [Chunking Strategies README](/home/runner/_work/ScareVerseLab/ScareVerseLab/backend/app/workflows/chunking_strategies/README.md)
- [Embeddings Generation README](/home/runner/_work/ScareVerseLab/ScareVerseLab/backend/app/workflows/generate_embeddings_and_store/README.md)
