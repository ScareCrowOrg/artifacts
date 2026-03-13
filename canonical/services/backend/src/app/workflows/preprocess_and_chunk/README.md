---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - workflows
  - preprocessing
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Preprocess and Chunk Module

## Overview

The `preprocess_and_chunk` module provides comprehensive document preprocessing and intelligent chunking functionality for RAG (Retrieval-Augmented Generation) ingestion. It supports multiple file types with specialized chunking strategies.

## Architecture

The module is organized into specialized components:

```
app/workflows/preprocess_and_chunk/
├── __init__.py           # Public API exports (63 lines)
├── loader.py             # File loading (68 lines)
├── preprocessor.py       # Text preprocessing (47 lines)
├── chunker.py            # Intelligent chunking (198 lines)
├── output_handler.py     # JSON output generation (76 lines)
├── pipeline.py           # PipelineItem execution (168 lines)
├── cli.py                # Command-line interface (142 lines)
└── README.md            # This file
```

## Components

### Loader (loader.py)

Handles loading file content from different file types.

**Key Functions:**
- `generate_document_id()` - Generate unique UUID for documents
- `load_file_content(file_path, file_type)` - Load content based on type (PDF, text, etc.)

**Supported File Types:**
- PDF (via pypdf library)
- Text-based files (UTF-8)

### Preprocessor (preprocessor.py)

Performs basic text preprocessing operations.

**Key Functions:**
- `preprocess_text(content)` - Normalize line endings, remove excessive blank lines

**Operations:**
- Normalize line endings (CRLF → LF)
- Remove excessive blank lines (max 2 consecutive)
- Strip trailing whitespace from lines

### Chunker (chunker.py)

Intelligent file-type-specific chunking strategies.

**Key Functions:**
- `chunk_text_intelligent(content, file_path, file_type, document_id, ...)` - Dispatch to specialized chunkers
- `_is_frontend_js_file(file_path, file_type)` - Detect Vue.js frontend files

**Chunking Strategies:**
- **Markdown**: Semantic chunking with MarkdownHeaderTextSplitter
- **Python**: AST-based chunking with docstring extraction
- **Vue.js**: SFC, composable, and Pinia store chunking
- **Config**: Structured chunking for YAML/JSON/ENV
- **Code**: Generic chunking for JS/TS/Java/C++/Go/Rust
- **Docs**: Generic chunking for TXT/RST/ADOC/PDF

**Output:**
- Returns `(doc_chunks, code_chunks)` tuple
- Each chunk includes `content` and `metadata`
- Chunks are targeted to appropriate collections (scareverse_docs, scareverse_code)

### Output Handler (output_handler.py)

Saves chunks to JSON files.

**Key Functions:**
- `save_chunks_to_separate_json_files(doc_chunks, code_chunks, ...)` - Save to separate files
- `save_chunks_to_json(chunks, output_dir, document_id)` - Save to single file

### Pipeline (pipeline.py)

Provides PipelineItem execute function for workflow integration.

**Key Functions:**
- `execute(item: PipelineItem) -> PipelineItem` - Main workflow entry point

**Features:**
- Extracts parameters from `item.data`
- Executes full preprocessing and chunking pipeline
- Updates `item.data` with results
- Adds execution fragments for traceability
- Error handling with detailed logging

### CLI (cli.py)

Command-line interface for standalone execution.

**Key Functions:**
- `main()` - Parse arguments and execute pipeline

**Usage:**
```bash
python -m app.workflows.preprocess_and_chunk.cli \
  --file-path /path/to/document.md \
  --file-type markdown \
  --output-dir /tmp/chunks \
  --chunk-size 1000 \
  --chunk-overlap 200
```

## Usage Examples

### As a Module (Python)

```python
from app.workflows.preprocess_and_chunk import (
    load_file_content,
    preprocess_text,
    chunk_text_intelligent,
    save_chunks_to_separate_json_files
)
from pathlib import Path

# Load and preprocess
content = load_file_content(Path("document.md"), "markdown")
preprocessed = preprocess_text(content)

# Chunk intelligently
doc_chunks, code_chunks = chunk_text_intelligent(
    preprocessed,
    Path("document.md"),
    "markdown",
    "doc-12345",
    chunk_size=1000,
    chunk_overlap=200
)

# Save to files
doc_path, code_path = save_chunks_to_separate_json_files(
    doc_chunks, code_chunks, Path("/tmp"), "doc-12345"
)
```

### As a Workflow (PipelineItem)

```python
from app.workflows.preprocess_and_chunk import execute
from app.core.models import PipelineItem

# Create PipelineItem with data
item = PipelineItem(
    data={
        "file_path": "/path/to/document.py",
        "file_type": "python",
        "output_dir": "/tmp/chunks",
        "chunk_size": 1000,
        "chunk_overlap": 200
    }
)

# Execute workflow
result_item = execute(item)

# Check results
if result_item.error:
    print(f"Error: {result_item.error}")
else:
    print(f"Doc chunks: {result_item.data['num_doc_chunks']}")
    print(f"Code chunks: {result_item.data['num_code_chunks']}")
    print(f"Output: {result_item.data['doc_chunks_path']}")
```

### As a CLI Tool

```bash
# Process a markdown file
python -m app.workflows.preprocess_and_chunk.cli \
  --file-path README.md \
  --file-type markdown \
  --output-dir ./chunks

# Process a Python file with custom chunk size
python -m app.workflows.preprocess_and_chunk.cli \
  --file-path main.py \
  --file-type python \
  --chunk-size 1500 \
  --chunk-overlap 300 \
  --output-dir ./chunks

# Process a PDF
python -m app.workflows.preprocess_and_chunk.cli \
  --file-path document.pdf \
  --file-type pdf \
  --output-dir ./chunks \
  --document-id custom-doc-id
```

## File Type Support

| File Type | Chunking Strategy | Target Collection | Model |
|-----------|------------------|-------------------|-------|
| Markdown (.md) | Semantic (headers) | scareverse_docs | mistral |
| Python (.py) | AST-based | scareverse_code | deepseek-coder |
| Vue (.vue) | SFC parsing | scareverse_code | deepseek-coder |
| JS/TS Frontend | Composables/Stores | scareverse_code | deepseek-coder |
| Config (.yml, .json, .env) | Structured | scareverse_code | deepseek-coder |
| Code (.js, .ts, .java, .cpp, .go, .rs) | Generic | scareverse_code | deepseek-coder |
| Docs (.txt, .rst, .adoc, .pdf) | Generic | scareverse_docs | mistral |

## Output Format

### Chunk Structure

Each chunk is a dictionary with:
```json
{
  "content": "Chunk text content...",
  "metadata": {
    "chunk_id": "0",
    "document_id": "doc-12345",
    "source": "/path/to/file.md",
    "file_type": "markdown",
    "chunk_index": 0,
    "char_count": 850,
    "embedding_model_id": "mistral",
    "target_collection": "scareverse_docs"
  }
}
```

### JSON Files

Chunks are saved to separate JSON files:
- `{document_id}_doc_chunks.json` - Documentation chunks
- `{document_id}_code_chunks.json` - Code chunks

## Configuration

### Chunk Parameters

- `chunk_size` (int, default: 1000) - Maximum chunk size in characters
- `chunk_overlap` (int, default: 200) - Overlap between chunks
- `output_dir` (Path, default: /tmp) - Output directory for JSON files
- `document_id` (str, default: UUID) - Unique document identifier

### Frontend File Detection

Frontend JS/TS files are detected based on path patterns:
- `cockpit-vue/src/composables/`
- `cockpit-vue/src/stores/`
- `cockpit-vue/src/components/`
- `cockpit/src/composables/`
- `cockpit/src/stores/`

## Error Handling

All modules handle errors consistently:
- `FileNotFoundError` - File doesn't exist
- `ValueError` - Unsupported file type or encoding issues
- `ImportError` - Missing dependencies (chunking strategies)
- Detailed logging of all errors with tracebacks

## Dependencies

- `pypdf` - PDF file reading
- `langchain_text_splitters` - Generic text chunking
- `app.workflows.chunking_strategies` - Specialized chunkers (Markdown, Python, Config)
- `app.workflows.vue_chunking_strategies` - Vue.js specialized chunking
- `app.core.models` - PipelineItem (optional, for workflow integration)

## Testing

Tests for this module are located in:
- `tests/unit/backend/workflows/test_preprocessing_workflow.py` - Unit tests
- `tests/integration/backend/test_vue_preprocessing_integration.py` - Integration tests

Run tests:
```bash
pytest tests/unit/backend/workflows/test_preprocessing_workflow.py -v
```

## File Size Compliance

All files in this module are under 500 lines (Rule 1.1):
- `loader.py`: 68 lines ✅
- `preprocessor.py`: 47 lines ✅
- `chunker.py`: 198 lines ✅
- `output_handler.py`: 76 lines ✅
- `pipeline.py`: 168 lines ✅
- `cli.py`: 142 lines ✅
- `__init__.py`: 63 lines ✅

**Total:** 762 lines across 7 modules (previously 650 lines in 1 file)

## Migration Guide

### Before (Monolithic)

```python
from app.workflows.preprocess_and_chunk import (
    load_file_content,
    chunk_text_intelligent,
    execute
)

result = execute(pipeline_item)
```

### After (Modularized)

```python
# Public API remains the same - no code changes needed!
from app.workflows.preprocess_and_chunk import (
    load_file_content,
    chunk_text_intelligent,
    execute
)

result = execute(pipeline_item)
```

The modularization is **fully backward compatible**. All existing code continues to work without modification.

## Internal Module Access (Advanced)

If you need direct access to specialized modules:

```python
from app.workflows.preprocess_and_chunk.loader import load_file_content
from app.workflows.preprocess_and_chunk.preprocessor import preprocess_text
from app.workflows.preprocess_and_chunk.chunker import chunk_text_intelligent
from app.workflows.preprocess_and_chunk.output_handler import save_chunks_to_separate_json_files
from app.workflows.preprocess_and_chunk.pipeline import execute
from app.workflows.preprocess_and_chunk.cli import main

# Direct module usage
content = load_file_content(Path("file.md"), "markdown")
```

## Future Enhancements

- Add streaming support for large files
- Implement chunk size optimization based on content
- Add support for more file types (DOCX, PPTX, HTML)
- Parallel chunking for multiple files
- Chunk quality metrics and validation
- Deduplication of similar chunks

## References

- [chunking_strategies.py](../chunking_strategies.py) - Markdown, Python, Config chunkers
- [vue_chunking_strategies.py](../vue_chunking_strategies.py) - Vue.js specialized chunking
- [RULESET.md](../../../RULESET.md) - Project rules
- [ARQUITETURA_TESTES.md](../../../docs/ARQUITETURA_TESTES.md) - Test architecture
