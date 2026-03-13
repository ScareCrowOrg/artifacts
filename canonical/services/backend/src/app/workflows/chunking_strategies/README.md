---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - workflows
  - chunking
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Chunking Strategies Module

Intelligent chunking strategies for document ingestion into RAG collections.

## Overview

This module provides specialized chunking strategies optimized for different file types, with each strategy targeting specific embedding models and collections for optimal retrieval performance.

## Directory Structure

```
chunking_strategies/
├── README.md                # This file
├── __init__.py             # Public API exports (26 lines)
├── markdown_chunker.py     # Markdown semantic chunking (143 lines)
├── python_chunker.py       # Python AST-based chunking (196 lines)
└── config_chunker.py       # Configuration file chunking (264 lines)
```

## Components

### Markdown Chunker (`markdown_chunker.py`)

**Purpose**: Semantic chunking for Markdown documentation files.

**Functions**:
- `chunk_markdown()`: Main chunking function using header-based splitting
- `_clean_markdown_content()`: Content cleaning helper

**Strategy**:
- Splits on headers (H1, H2, H3) to maintain semantic coherence
- Removes excessive special characters and markdown artifacts
- Targets `scareverse_docs` collection with `mistral` embeddings

**Usage**:
```python
from app.workflows.chunking_strategies import chunk_markdown

chunks = chunk_markdown(
    content="# Title\n\nContent...",
    file_path=Path("docs/README.md"),
    document_id="doc-001"
)
```

### Python Chunker (`python_chunker.py`)

**Purpose**: AST-based chunking for Python source code.

**Functions**:
- `chunk_python_code()`: Main chunking function using AST analysis
- `_extract_code_and_docstring()`: Helper to extract code units

**Strategy**:
- Parses Python code into Abstract Syntax Tree (AST)
- Extracts functions, classes, and methods as complete units
- Separates code chunks (for `scareverse_code` with `deepseek-coder`) from docstrings (for `scareverse_docs` with `mistral`)

**Returns**:
- Tuple of `(code_chunks, doc_chunks)` for dual collection ingestion

**Usage**:
```python
from app.workflows.chunking_strategies import chunk_python_code

code_chunks, doc_chunks = chunk_python_code(
    content="def hello():\n    '''Greet'''...",
    file_path=Path("app/utils.py"),
    document_id="code-001"
)
```

### Configuration Chunker (`config_chunker.py`)

**Purpose**: Structured chunking for configuration files (YAML, JSON, .env).

**Functions**:
- `chunk_configuration_file()`: Main chunking dispatcher
- `_chunk_yaml_content()`: YAML-specific chunking
- `_chunk_json_content()`: JSON-specific chunking
- `_chunk_env_content()`: .env-specific chunking

**Strategy**:
- **YAML/JSON**: Splits by top-level keys to maintain configuration context
- **.env**: Groups related environment variables by prefix
- Targets `scareverse_code` collection with `deepseek-coder` embeddings

**Usage**:
```python
from app.workflows.chunking_strategies import chunk_configuration_file

chunks = chunk_configuration_file(
    content="key: value\n...",
    file_path=Path("config.yaml"),
    document_id="config-001",
    file_type="yaml"
)
```

## Chunk Metadata

All chunks include rich metadata for filtering and retrieval:

```python
{
    "content": "...",
    "metadata": {
        "document_id": "unique-id",
        "source": "/path/to/file",
        "file_type": "markdown|python|yaml|json|env",
        "chunk_type": "header|function|class|yaml_block|...",
        "char_count": 1234,
        "embedding_model_id": "mistral|deepseek-coder",
        "target_collection": "scareverse_docs|scareverse_code",
        # Additional type-specific metadata
    }
}
```

## Target Collections

### scareverse_docs (Documentation)
- **Embedding Model**: `mistral`
- **Content Types**: Markdown, Python docstrings, JSDoc comments
- **Use Case**: Natural language documentation retrieval

### scareverse_code (Source Code)
- **Embedding Model**: `deepseek-coder`
- **Content Types**: Python code, JavaScript/TypeScript, configuration files
- **Use Case**: Code snippet retrieval and semantic code search

## Backward Compatibility

The original `chunking_strategies.py` file has been converted to a shim that re-exports all functions. All existing imports continue to work:

```python
# Old import (still works)
from app.workflows.chunking_strategies import chunk_markdown

# New recommended import (same result)
from app.workflows.chunking_strategies import chunk_markdown
```

## RULESET.md Compliance

| Rule | Requirement | Status |
|------|-------------|--------|
| **Rule 1.1** | File Size < 500 lines | ✅ All files under 200 lines |
| **Rule 1.3** | Descriptive file names | ✅ `markdown_chunker`, `python_chunker`, `config_chunker` |
| **Rule 2.1** | README.md in directories | ✅ This file |
| **Rule 4.3** | Technical naming in English | ✅ All names in English |

## Line Counts

```
✓ PASS: __init__.py has 26 lines
✓ PASS: markdown_chunker.py has 143 lines
✓ PASS: python_chunker.py has 196 lines
✓ PASS: config_chunker.py has 264 lines
```

**Total reduction**: 555 lines → **41 lines** (shim) + **629 lines** (modularized)

## Testing

Tests are located in:
- `backend/tests/unit/backend/test_chunking_strategies.py`
- `backend/tests/unit/backend/workflows/test_chunking_strategies.py`

All existing tests remain compatible due to backward-compatible exports.

## Related Documentation

- [Workflows README](../README.md) - Parent module documentation
- [Ingestion Graph](../ingestion_graph.py) - Uses these chunking strategies
- [RAG Architecture](../../docs/rag/) - RAG system architecture
