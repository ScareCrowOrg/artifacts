---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - rag
  - vectorstore
  - embeddings
  - ollama
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Document Ingestion - RAG Vector Store Setup

This document details the document ingestion system for building the RAG (Retrieval Augmented Generation) vector store using ChromaDB and Ollama embeddings.

## Overview

The document ingestion system recursively processes files from the project directory, chunks them intelligently, generates embeddings using local Ollama models, and stores them in ChromaDB for efficient semantic search.

## Prerequisites - Ollama Setup

### Installing Ollama

The RAG system uses **Ollama** for local embeddings, eliminating the need for external API keys and costs.

#### Installation Steps

1. **Download and Install Ollama**
   - Visit [https://ollama.ai/](https://ollama.ai/)
   - Download the installer for your OS (Linux, macOS, Windows)
   - Follow installation instructions

2. **Verify Installation**
   ```bash
   ollama --version
   ```

3. **Pull Embedding Models**
   
   The system supports three models for embeddings:
   
   ```bash
   # Mistral (default, recommended for general use)
   ollama pull mistral
   
   # Phi (lightweight, fast)
   ollama pull phi
   
   # DeepSeek Coder (optimized for code)
   ollama pull deepseek-coder
   ```

4. **Start Ollama Service**
   ```bash
   ollama serve
   ```
   
   By default, Ollama runs on `http://localhost:11434`

5. **Verify Model**
   ```bash
   ollama list
   ```
   
   You should see the models you pulled.

### Configuration

Set environment variables in `.env` (see `.env.example`):

```bash
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=mistral  # or phi, deepseek-coder

# RAG Configuration
VECTORSTORE_PATH=chroma_db
VECTORSTORE_COLLECTION=scareverse_docs
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

## Features

- Recursive traversal of directories starting from BASE_DIR
- Support for all text files (UTF-8) and PDFs
- Automatic chunking with `RecursiveCharacterTextSplitter` (configurable chunk_size and overlap)
- **Ollama local embeddings** (mistral, phi, deepseek-coder)
- **Incremental ingestion**: Only new or modified chunks are processed
- ChromaDB persistence at `chroma_db/` (configurable)
- Binary file detection and skipping

## Usage

### Basic Ingestion

```python
from backend.app.utils.document_ingestion import (
    ingest_documents_to_vectorstore, 
    get_or_create_vectorstore
)

# Ingest documents from BASE_DIR with default model (mistral)
vectorstore = ingest_documents_to_vectorstore()

# Use specific embedding model
vectorstore = ingest_documents_to_vectorstore(embedding_model='phi')

# Ingest from specific directory
vectorstore = ingest_documents_to_vectorstore(
    directory_path="/path/to/docs",
    vectorstore_path="my_chroma_db",
    collection_name="my_collection"
)
```

### Advanced Options

```python
# Force recreate (delete existing and rebuild)
vectorstore = ingest_documents_to_vectorstore(
    force_recreate=True,
    embedding_model='deepseek-coder'
)

# Custom chunking parameters
vectorstore = ingest_documents_to_vectorstore(
    chunk_size=1500,
    chunk_overlap=300
)

# Get existing vectorstore without ingestion
vectorstore = get_or_create_vectorstore(
    embedding_model='mistral',
    vectorstore_path='chroma_db',
    collection_name='scareverse_docs'
)
```

### Searching Documents

```python
# Similarity search
docs = vectorstore.similarity_search(
    query="How do I authenticate users?",
    k=5  # Return top 5 most relevant chunks
)

for doc in docs:
    print(f"Source: {doc.metadata['source']}")
    print(f"Content: {doc.page_content[:200]}...")
    print("---")

# Search with scores
docs_with_scores = vectorstore.similarity_search_with_score(
    query="Authentication implementation",
    k=3
)

for doc, score in docs_with_scores:
    print(f"Score: {score}")
    print(f"Source: {doc.metadata['source']}")
    print(f"Content: {doc.page_content[:150]}...")
    print("---")
```

## Supported File Types

- **Text files**: `.md`, `.txt`, `.py`, `.js`, `.ts`, `.json`, `.yaml`, `.yml`, `.toml`, `.env`, `.sh`, `.bat`, `.ps1`
- **PDFs**: `.pdf` (extracted text only, no images)
- **Others**: Any UTF-8 encoded text file

Binary files (images, videos, executables, archives) are automatically skipped.

## Document Chunking

Documents are split into chunks using `RecursiveCharacterTextSplitter` for better semantic preservation:

```python
# Default settings
chunk_size = 1000        # Characters per chunk
chunk_overlap = 200      # Overlap between chunks

# Chunking process:
# 1. Try to split on paragraph boundaries (\n\n)
# 2. Then on sentence boundaries (. ! ?)
# 3. Then on line boundaries (\n)
# 4. Finally on character boundaries if needed
```

**Why chunking?**
- Embeddings work better on focused, coherent text
- Improves retrieval relevance
- Manages token limits for embedding models

## Incremental Ingestion

The system supports **incremental updates** using chunk IDs:

```python
# First run: Ingests all documents
vectorstore = ingest_documents_to_vectorstore()

# Subsequent runs: Only processes new/modified documents
# Existing chunks are skipped (based on content hash)
vectorstore = ingest_documents_to_vectorstore()

# Force full rebuild if needed
vectorstore = ingest_documents_to_vectorstore(force_recreate=True)
```

Chunk IDs are generated from:
- File path
- Chunk content hash (MD5)
- Chunk index

This ensures:
- No duplicate chunks in vector store
- Efficient updates (only new/modified content)
- Proper cleanup when files are deleted

## Metadata

Each document chunk stores metadata:

```python
{
    'source': 'backend/app/main.py',
    'chunk_index': 0,
    'chunk_id': 'backend/app/main.py:0:abc123...',
    'file_type': '.py'
}
```

Use metadata for filtering:

```python
# Search only in Python files
docs = vectorstore.similarity_search(
    query="FastAPI router implementation",
    k=5,
    filter={'file_type': '.py'}
)
```

## Performance Considerations

### Model Selection

| Model | Speed | Quality | Use Case |
|-------|-------|---------|----------|
| **mistral** | Medium | High | General purpose (recommended) |
| **phi** | Fast | Medium | Quick prototyping, large corpora |
| **deepseek-coder** | Slow | Highest | Code-specific queries |

### Optimization Tips

1. **Use phi for initial ingestion** (faster), switch to mistral for production
2. **Adjust chunk size**: Larger chunks = fewer embeddings = faster ingestion
3. **Incremental updates**: Don't use `force_recreate=True` unless necessary
4. **Batch processing**: System automatically batches embeddings for efficiency

### Typical Ingestion Times

- Small project (~100 files, 10MB): 2-5 minutes (mistral)
- Medium project (~500 files, 50MB): 10-20 minutes (mistral)
- Large project (~1000+ files, 100MB+): 30-60 minutes (mistral)

Use `phi` for 2-3x faster ingestion at slight quality cost.

## Troubleshooting

### Ollama Not Running

```
Error: Could not connect to Ollama at http://localhost:11434
```

**Solution:**
1. Verify Ollama is installed: `ollama --version`
2. Start Ollama service: `ollama serve`
3. Check it's running: `curl http://localhost:11434/api/tags`

### Model Not Found

```
Error: model 'mistral' not found
```

**Solution:**
```bash
# Pull the model
ollama pull mistral

# Verify it's available
ollama list
```

### Vector Store Not Found

```
FileNotFoundError: Vector store not found at chroma_db/
```

**Solution:**
```bash
# Run ingestion to create vector store
python ingest.py

# Or in code
from backend.app.utils import ingest_documents_to_vectorstore
vectorstore = ingest_documents_to_vectorstore()
```

### Slow Ingestion

If ingestion is taking too long:

1. **Use a faster model**: Switch to `phi` for faster processing
   ```python
   vectorstore = ingest_documents_to_vectorstore(embedding_model='phi')
   ```

2. **Reduce chunk size**: Fewer, larger chunks process faster
   ```bash
   # In .env
   CHUNK_SIZE=2000
   CHUNK_OVERLAP=100
   ```

3. **Use incremental ingestion**: Don't use `force_recreate=True` unless necessary
   ```python
   # Only processes new/modified documents
   vectorstore = ingest_documents_to_vectorstore()
   ```

### Switching Embedding Models

**IMPORTANT:** When switching models, you must recreate the vector store:

```python
# Embeddings from different models are not compatible
vectorstore = ingest_documents_to_vectorstore(
    embedding_model='phi',
    force_recreate=True  # Required when changing models
)
```

## Command-Line Ingestion

Use the included `ingest.py` script for command-line ingestion:

```bash
# Basic ingestion with defaults
python ingest.py

# With specific model
python ingest.py --model phi

# Force recreate
python ingest.py --force-recreate

# Custom directory
python ingest.py --directory /path/to/docs

# Custom output path
python ingest.py --output my_vector_db
```

## Related Documentation

- [Input Processor](./INPUT_PROCESSOR.md) - How to use the ingested documents for RAG
- [Conversation Memory](./CONVERSATION_MEMORY.md) - Managing conversation context
- [Main README](./README.md) - Utils module overview
- [RAG Service](../services/README.md) - High-level RAG service
