---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - utils
  - rag
  - memory
  - documentation-index
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Utils Module - RAG, Conversational Memory, and Chat Utilities

This module provides utilities for Retrieval Augmented Generation (RAG), conversational memory management, and intelligent chat processing in the ScareVerse backend.

## Index

### Files
- `__init__.py` - Module exports and initialization
- `chat_utils.py` - Chat-related utility functions
- `conversation_memory.py` - LangChain-based memory with automatic summarization (uses Ollama/Mistral)
- `document_ingestion.py` - Document ingestion into ChromaDB vector store with Ollama embeddings
- `input_processor.py` - Priority-based RAG context retrieval
- `rate_limiter.py` - Rate limiting and batch processing utilities for Ollama requests
- `trace_export.py` - Conversation trace export and analysis utilities

### Documentation
- [DOCUMENT_INGESTION.md](./DOCUMENT_INGESTION.md) - Complete guide to RAG vector store setup and document ingestion
- [INPUT_PROCESSOR.md](./INPUT_PROCESSOR.md) - Priority-based context retrieval for RAG
- [CONVERSATION_MEMORY.md](./CONVERSATION_MEMORY.md) - LangChain-based conversation memory management
- [RATE_LIMITER.md](#rate-limiting) - Rate limiting for Ollama embedding generation
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Common issues and solutions

## Overview

The utils module consists of three main components:

1. **Document Ingestion** - Ingests documents into ChromaDB vector store with Ollama embeddings for RAG
2. **Input Processor** - Processes user input with 3-tier priority-based RAG (attached files → file references → general search)
3. **Conversation Memory** - LangChain-based memory with automatic summarization using Ollama/Mistral (cost-free)

## Quick Start

### 1. Setup Ollama

Install Ollama and pull required models:

```bash
# Install Ollama from https://ollama.ai/

# Pull embedding model (choose one)
ollama pull mistral  # Recommended: balanced speed and quality
ollama pull phi      # Faster: lightweight option
ollama pull deepseek-coder  # Best for code-specific queries

# Start Ollama service
ollama serve
```

### 2. Configure Environment

Set environment variables in `.env`:

```bash
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=mistral

# RAG Configuration
VECTORSTORE_PATH=chroma_db
VECTORSTORE_COLLECTION=scareverse_docs
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### 3. Ingest Documents

Build the RAG vector store:

```bash
# From project root
python ingest.py

# Or in code
from backend.app.utils.document_ingestion import ingest_documents_to_vectorstore
vectorstore = ingest_documents_to_vectorstore()
```

### 4. Use RAG in Your Code

```python
from backend.app.utils.input_processor import process_user_input
from backend.app.utils.document_ingestion import get_or_create_vectorstore
from backend.app.utils.conversation_memory import get_session_memory

# Load vector store
vectorstore = get_or_create_vectorstore()

# Get session memory
memory = get_session_memory(session_id="user_123")

# Process user input with RAG
processed_msg, context_docs = process_user_input(
    user_message="How does authentication work?",
    vectorstore=vectorstore,
    k=5  # Retrieve top 5 relevant chunks
)

# Use context in your LLM prompt
# (Orchestrator handles this automatically)

# Update conversation memory
memory.add_exchange(
    user_message=processed_msg,
    ai_response=ai_response
)
```

## Memory Management Architecture

The project uses **LangChain-Based Memory** (`conversation_memory.py`) as the PRIMARY approach:

**Features:**
- Automatic summarization when token limit is reached
- Session-based memory with multi-user support
- Uses **Ollama/Mistral by default** for cost-free local summarization
- Integration with LangChain `ConversationSummaryBufferMemory`
- No manual threshold management required

**Benefits:**
- ✅ Zero API costs (uses local Ollama)
- ✅ Fully automatic memory management
- ✅ Battle-tested LangChain implementation
- ✅ Privacy-preserving (data never leaves server)

📚 **Detailed Documentation**: [CONVERSATION_MEMORY.md](./CONVERSATION_MEMORY.md)

## Priority-Based RAG

The Input Processor implements a **3-tier priority system** for context retrieval:

1. **Priority 1: Attached Files** (highest) - Files explicitly attached by user via UI
2. **Priority 2: File References** - Files referenced with `#path/to/file.ext` syntax in messages
3. **Priority 3: General RAG** - Semantic similarity search across all documents

**Example:**

```python
# Priority 1: Attached file takes precedence
attached_files = [{'path': 'report.pdf', 'content': '...'}]
processed_msg, docs = process_user_input(
    user_message="Analyze this report",
    attached_files=attached_files,
    vectorstore=vectorstore
)

# Priority 2: File reference extracts specific file
processed_msg, docs = process_user_input(
    user_message="Check #docs/README.md for setup",
    vectorstore=vectorstore
)

# Priority 3: General semantic search
processed_msg, docs = process_user_input(
    user_message="How does authentication work?",
    vectorstore=vectorstore
)
```

📚 **Detailed Documentation**: [INPUT_PROCESSOR.md](./INPUT_PROCESSOR.md)

## Document Ingestion

### Features

- Recursive directory traversal from BASE_DIR
- Support for text files (`.md`, `.py`, `.js`, `.txt`, `.json`, etc.) and PDFs
- Automatic chunking with configurable size and overlap
- **Ollama local embeddings** (mistral, phi, deepseek-coder)
- **Incremental ingestion**: Only new or modified chunks are processed
- ChromaDB persistence with metadata

### Usage

```python
from backend.app.utils.document_ingestion import (
    ingest_documents_to_vectorstore,
    get_or_create_vectorstore
)

# Basic ingestion with default settings
vectorstore = ingest_documents_to_vectorstore()

# Use specific embedding model
vectorstore = ingest_documents_to_vectorstore(embedding_model='phi')

# Force recreate (when switching models or major changes)
vectorstore = ingest_documents_to_vectorstore(force_recreate=True)

# Get existing vectorstore without re-ingestion
vectorstore = get_or_create_vectorstore()

# Search documents
docs = vectorstore.similarity_search("authentication", k=5)
```

📚 **Detailed Documentation**: [DOCUMENT_INGESTION.md](./DOCUMENT_INGESTION.md)

## Rate Limiting

The rate limiter provides batch processing with controlled delays to prevent overwhelming Ollama with too many concurrent embedding generation requests.

### Quick Start

```python
from backend.app.utils.rate_limiter import create_embedding_rate_limiter

# Create rate limiter with config defaults
limiter = create_embedding_rate_limiter()

# Process items in rate-limited batches
def process_batch(batch):
    # Your processing logic here
    return len(batch)

results = limiter.process_in_batches(items, process_batch)
```

### Configuration

Set environment variables in `.env`:

```bash
# Rate Limiting Configuration (prevents server crashes)
EMBEDDING_BATCH_SIZE=10        # Chunks per batch
EMBEDDING_BATCH_DELAY=0.5      # Seconds between batches
EMBEDDING_MAX_CONCURRENT=1     # Max concurrent requests
```

### Features

- **Batch Processing**: Groups items into configurable batches
- **Rate Limiting**: Adds configurable delays between batches
- **Concurrency Control**: Limits simultaneous operations
- **Exponential Backoff**: Efficient waiting when at capacity
- **Statistics Tracking**: Monitor requests and batches processed

### Use Cases

The rate limiter is automatically used in:
- Embedding generation (`embeddings_chromadb_store.py`)
- Document ingestion (`document_ingestion.py`)

For manual usage:

```python
from backend.app.utils.rate_limiter import RateLimiter

# Custom configuration
limiter = RateLimiter(
    batch_size=20,      # 20 items per batch
    batch_delay=1.0,    # 1 second between batches
    max_concurrent=2    # 2 concurrent operations
)

# Process with progress tracking
results = limiter.process_in_batches(
    items,
    process_func,
    progress_callback=lambda curr, total: print(f"{curr}/{total}")
)

# Get statistics
stats = limiter.get_stats()
print(f"Processed {stats['total_requests']} requests")
```

📚 **Detailed Documentation**: See [docs/summaries/rate-limiting-implementation.md](../../../../docs/summaries/rate-limiting-implementation.md)

## Integration with Orchestrator

The utils module integrates seamlessly with the Chat Orchestrator:

```python
from backend.app.orchestrator import ChatOrchestrator

orchestrator = ChatOrchestrator()

# The orchestrator automatically:
# 1. Processes input with priority-based RAG
# 2. Retrieves session memory
# 3. Includes conversation history in prompts
# 4. Updates memory after each response
# 5. Triggers automatic summarization when needed

result = orchestrator.process(
    mensagem="Continue our discussion",
    responsavel_id="user123",
    modelo="mistral",
    session_id="session_123"
)
```

## Configuration

All configuration is centralized in `.env`:

```bash
# Ollama Settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=mistral  # or phi, deepseek-coder
OLLAMA_MODEL=mistral  # Model for chat/summarization

# RAG Settings
VECTORSTORE_PATH=chroma_db
VECTORSTORE_COLLECTION=scareverse_docs
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Memory Settings
MEMORY_MAX_TOKEN_LIMIT=3000

# Rate Limiting Settings (prevents server crashes during embedding generation)
EMBEDDING_BATCH_SIZE=10        # Chunks per batch
EMBEDDING_BATCH_DELAY=0.5      # Seconds between batches  
EMBEDDING_MAX_CONCURRENT=1     # Max concurrent requests
```

## File Structure

```
backend/app/utils/
├── README.md                    # This file (overview and quick start)
├── DOCUMENT_INGESTION.md        # Complete ingestion guide
├── INPUT_PROCESSOR.md           # Priority-based RAG guide
├── CONVERSATION_MEMORY.md       # Memory management guide
├── TROUBLESHOOTING.md           # Common issues and solutions
├── __init__.py                  # Module exports
├── chat_utils.py                # Chat utility functions
├── conversation_memory.py       # LangChain-based memory
├── document_ingestion.py        # Document ingestion logic
├── input_processor.py           # Priority-based RAG processor
├── rate_limiter.py              # Rate limiting utilities
└── trace_export.py              # Trace export utilities
```

## Testing

```bash
# Unit tests
pytest tests/unit/test_document_ingestion.py
pytest tests/unit/test_conversation_memory.py
pytest tests/unit/test_input_processor.py
pytest tests/unit/backend/utils/test_rate_limiter.py

# Integration tests
pytest tests/integration/test_rag_integration.py

# With coverage
pytest --cov=backend.app.utils --cov-report=html
```

## Performance Considerations

### Embedding Model Selection

| Model | Speed | Quality | Use Case |
|-------|-------|---------|----------|
| **mistral** | Medium | High | General purpose (recommended) |
| **phi** | Fast | Medium | Quick prototyping, large corpora |
| **deepseek-coder** | Slow | Highest | Code-specific queries |

### Typical Ingestion Times

- Small project (~100 files): 2-5 minutes (mistral)
- Medium project (~500 files): 10-20 minutes (mistral)
- Large project (~1000+ files): 30-60 minutes (mistral)

Use `phi` for 2-3x faster ingestion at slight quality cost.

### Memory Usage

- Each session stores conversation history in memory
- Automatic summarization keeps history bounded
- Token limit default: 3000 tokens (configurable)
- Typical memory per session: 1-5 MB

## Troubleshooting

Common issues and solutions are documented in [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

**Quick fixes:**

- **Ollama not running**: `ollama serve`
- **Model not found**: `ollama pull mistral`
- **Vector store not found**: `python ingest.py`
- **Slow ingestion**: Use `phi` model or increase `CHUNK_SIZE`
- **No context retrieved**: Check vector store exists and documents are ingested

For detailed solutions, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

## Cost Optimization ✅

**ALL operations use Ollama (local LLM) for zero API costs:**
- Document embeddings: Ollama embeddings (mistral, phi, deepseek-coder)
- Conversation summarization: Ollama/Mistral
- No external API keys required
- No per-token costs
- Privacy-preserving (data never leaves your server)

## Testing

### Running Tests

All utils modules have comprehensive test coverage (≥90% as per RULESET.md Rule 3.1).

**Run all utils tests:**
```bash
cd backend
pytest tests/unit/backend/utils/ -v --cov=app/utils --cov-report=term-missing
```

**Run specific module tests:**
```bash
# Conversation memory tests
pytest tests/unit/backend/utils/test_conversation_memory.py -v

# Trace export tests  
pytest tests/unit/backend/utils/test_trace_export.py -v
```

### Test Files

- `tests/unit/backend/utils/test_conversation_memory.py` - ConversationMemoryManager, SessionMemoryStore (40+ tests)
- `tests/unit/backend/utils/test_trace_export.py` - Trace export and analysis functions (20+ tests)

### Coverage Goals

All modules maintain ≥90% test coverage:
- `conversation_memory.py`: ~90% (requires langchain dependencies)
- `trace_export.py`: ~90%
- `chat_utils.py`: Covered via conversation_memory tests
- `document_ingestion.py`: Separate integration tests
- `input_processor.py`: Separate integration tests

### Test Dependencies

Tests require:
- `pytest` - Test framework
- `pytest-cov` - Coverage reporting
- `langchain`, `langchain_community` - For conversation_memory tests

Install test dependencies:
```bash
pip install pytest pytest-cov langchain langchain_community
```

## Related Documentation

- [Services Module](../services/README.md) - High-level RAG and AI services
- [Orchestrator](../orchestrator/README.md) - Chat orchestration
- [Routers](../routers/README.md) - API endpoints
- [Backend README](../../README.md) - Backend overview
- [Testing Guide](../../../../tests/README.md) - Testing documentation

## References

- [LangChain Documentation](https://python.langchain.com/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Ollama Documentation](https://ollama.ai/)
- [Project RULESET](../../../../RULESET.md)

---

**Last Updated**: 2025-11-17  
**Version**: 3.0 (Modularized documentation for compliance with 500-line limit)