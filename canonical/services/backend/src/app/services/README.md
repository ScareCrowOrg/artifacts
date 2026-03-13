---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - architecture
  - database
  - services
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Services Module

## Overview

This module contains business logic services for the ScareVerse backend, providing high-level abstractions for core functionality including advanced RAG with ensemble retrieval and external API integrations.

## Services

### Conversation Trace Service (`conversation_trace_service.py`) - **NEW**

**Structured Conversation Tracing for RAG Pipeline Observability**

Provides structured tracing of conversation flows through the RAG pipeline and LLM processing stages for observability and debugging.

**Features:**
- Trace cell creation for conversations
- Fragment recording at each pipeline stage
- Unique conversation ID generation
- Global enable/disable flag support
- Error handling and logging
- Singleton pattern for service instance

**Usage:**
```python
from backend.app.services.conversation_trace_service import get_conversation_trace_service

# Get service singleton
service = get_conversation_trace_service()

# Check if tracing is enabled
if service.is_tracing_enabled():
    # Generate conversation ID
    conv_id = service.generate_conversation_id(session_id="sess_123")
    
    # Create trace cell
    trace_cell = await service.create_trace_cell(
        conversation_id=conv_id,
        assignee_id="user_456",
        session_id="sess_123",
        user_message="How do I create a cell?",
        target_llm="openai"
    )
    
    # Record fragment at pipeline stage
    await service.record_fragment(
        trace_cell_id=trace_cell.id,
        stage="rag_retrieval",
        data={
            "query": "cell creation",
            "chunks_retrieved": 5,
            "collections_used": ["scareverse_docs"]
        },
        conversation_id=conv_id
    )
```

**Configuration:**
```python
# In .env or config.py
ENABLE_CONVERSATION_TRACING=false  # Default: disabled
```

**Fragment Structure:**
```python
{
    "timestamp": "2025-11-18T10:30:45.123456",
    "conversation_id": "conv_abc123",
    "stage": "rag_retrieval",
    "data": {
        # Stage-specific data
        "query": "...",
        "chunks_retrieved": 5
    }
}
```

**API:**
- `ConversationTraceService.is_tracing_enabled()` - Check if tracing is globally enabled
- `ConversationTraceService.generate_conversation_id()` - Generate unique conversation ID
- `ConversationTraceService.create_trace_cell()` - Create trace cell in database
- `ConversationTraceService.record_fragment()` - Record pipeline stage fragment
- `get_conversation_trace_service()` - Get singleton service instance

### RAG Service (`rag/` directory) - **MODULARIZED**

**Advanced RAG Service with CustomEnsembleRetriever**

Provides unified Retrieval Augmented Generation (RAG) operations with:
- **CustomEnsembleRetriever**: Multi-collection search across different file types (docs, code, config) using Reciprocal Rank Fusion
- **Dynamic Embedding Selection**: Automatically selects appropriate embedding model per collection
- **Query-based RAG**: Context retrieval for all LLMs (OpenAI, Gemini, Ollama)
- **No Temporary Collections**: Optimized approach without session-based temporary collections

**Modularization (2025-11-21) & LangChain 1.0+ Migration (2025-12-06):**
The RAG service has been modularized from a single 630-line file into a structured subdirectory:
- **`rag/config.py`** (35 lines) - Configuration and constants
- **`rag/embeddings.py`** (69 lines) - Embedding function management
- **`rag/retriever_manager.py`** (244 lines) - Retriever creation and ensemble logic
- **`rag/rag_service.py`** (388 lines) - Main RAGService class
- **`rag/ensemble_retriever.py`** (280 lines) - Custom EnsembleRetriever for LangChain 1.0+
- **`rag/__init__.py`** (32 lines) - Public API exports (backward compatible)
- **`rag/README.md`** - Detailed module documentation

**LangChain 1.0+ Migration:**
- Replaced deprecated `langchain.retrievers.EnsembleRetriever` with custom `CustomEnsembleRetriever`
- Implements Reciprocal Rank Fusion (RRF) algorithm for combining retriever results
- Fully compatible with LangChain 1.0+ `BaseRetriever` interface
- Provides backward compatibility methods for existing code

**Backward Compatibility:**
All existing imports continue to work unchanged:
```python
# Both work identically
from backend.app.services.rag_service import RAGService, get_rag_service
from backend.app.services.rag import RAGService, get_rag_service
```

**Features:**
- Multi-collection ensemble retrieval
- Dynamic embedding model selection per collection type
- Dual embedding support: Ollama (local) and OpenAI (API)
- Lazy-loaded retrievers for efficiency
- Session tracking support

**Usage:**
```python
from backend.app.services.rag_service import get_rag_service

# Create service with default collections (docs, code, config)
rag = get_rag_service()

# Custom collections with weights
rag = get_rag_service(
    collection_names=['scareverse_docs', 'scareverse_code'],
    ensemble_weights=[0.7, 0.3]  # 70% weight to docs, 30% to code
)

# Retrieve context using ensemble retrieval (all default collections)
message, docs, context = rag.get_context(
    user_message="Explain the API architecture",
    session_id="session_123",
    k=5  # Return top 5 most relevant documents
)

# Retrieve context from SPECIFIC collections only (NEW - Bug Fix)
# Only searches in the specified valid collections
message, docs, context = rag.get_context(
    user_message="Explain the API architecture",
    session_id="session_123",
    k=5,
    selected_collections=["scareverse_docs"]  # Search only in docs
)

# Use context in LLM prompt
prompt = f"Context:\n{context}\n\nQuestion: {message}"

# Direct similarity search in specific collection
similar_docs = rag.search_similar(
    query="authentication",
    collection_name="scareverse_docs",
    k=3
)
```

**Collection Filtering (Bug Fix - 2025-11-16):**
The `get_context()` method now properly filters collections based on user selection:
- Invalid collection names are automatically filtered out
- Only valid collections from `selected_collections` are used for search
- If all collections are invalid, falls back to default collections
- Non-default selections are not cached to ensure correct filtering each time
- Detailed logging shows which collections are actually used

**Real-World Example - Building a Code Assistant:**
```python
from backend.app.services.rag_service import get_rag_service
from backend.app.ollama_service import chat

# Initialize RAG with code-focused weights
rag = get_rag_service(
    collection_names=['scareverse_code', 'scareverse_docs'],
    ensemble_weights=[0.8, 0.2]  # Prioritize code over docs
)

# User asks about implementing a feature
user_question = "How do I implement file upload in the chat endpoint?"

# Retrieve relevant code examples and docs
_, docs, context = rag.get_context(
    user_message=user_question,
    session_id="dev_session_1",
    k=5
)

# Build prompt with context
system_prompt = f"""You are a code assistant. Use this codebase context to answer:

{context}

Provide code examples based on the existing patterns."""

# Generate response
response = chat(
    prompt=user_question,
    system_prompt=system_prompt,
    model="deepseek-coder"  # Code-specialized model
)

print(response)
```

**Collection Mapping:**
```python
COLLECTION_TO_EMBEDDING_MODEL = {
    'scareverse_docs': 'mistral',       # Documentation
    'scareverse_code': 'deepseek-coder', # Source code
    'scareverse_config': 'deepseek-coder', # Config files
}
```

**API:**
- `RAGService.__init__()` - Initialize with collections and weights
- `RAGService.get_context()` - Main entry point for RAG operations (uses CustomEnsembleRetriever)
- `RAGService.search_similar()` - Direct similarity search in specific or all collections
- `get_rag_service()` - Factory function for service creation
- `get_embedding_function_for_model_id()` - Get embedding function for a model ID

**For detailed module documentation, see:** [`rag/README.md`](./rag/README.md)

### OpenAI Files API (`openai_files_api.py`)

**OpenAI Files API Integration for Holistic File Contextualization**

Provides integration with OpenAI's Files API enabling file uploads for use with OpenAI models and Assistants API.

**Features:**
- File upload to OpenAI servers
- File deletion for cleanup
- File listing with filtering
- Async/await support

**Usage:**
```python
from backend.app.services.openai_files_api import (
    upload_file_to_openai_api,
    delete_file_from_openai_api,
    list_files_from_openai_api
)
from pathlib import Path

# Upload a file
file_id = await upload_file_to_openai_api(
    Path("documents/guide.pdf"),
    purpose="assistants"
)

# List uploaded files
files = await list_files_from_openai_api(purpose="assistants")

# Clean up when done
success = await delete_file_from_openai_api(file_id)
```

**API:**
- `upload_file_to_openai_api()` - Upload files to OpenAI
- `delete_file_from_openai_api()` - Delete files from OpenAI
- `list_files_from_openai_api()` - List uploaded files

### OpenAI Assistants API (`openai_assistant_service.py`) - **NEW**

**OpenAI Assistants API Integration for Holistic Conversation Management**

Provides integration with OpenAI's Assistants API for robust conversation management with native file contextualization via `file_id` references. This replaces the previous approach of injecting file content directly into prompts.

**Features:**
- Assistant creation and management
- Thread-based conversation management
- Native file attachment via `file_id`
- Run execution with automatic polling
- Message retrieval
- High-level orchestration function

**Key Benefits:**
- **Efficiency**: Files referenced by ID, not re-uploaded with each message
- **Native Context Management**: Threads maintain conversation history automatically
- **Holistic File Context**: Files persist across conversation turns
- **Alignment with "Everything is an Artifact"**: Files as first-class objects

**Usage:**
```python
from backend.app.services.openai_assistant_service import (
    process_with_assistant,
    create_or_get_assistant,
    create_thread,
    add_message_to_thread,
    run_assistant,
    get_run_messages
)
from pathlib import Path

# High-level usage (recommended)
response, thread_id, assistant_id = await process_with_assistant(
    user_message="Explain this code",
    file_paths=[Path("src/main.py")],
    system_instructions="You are a helpful code assistant.",
    model="gpt-4o-mini"
)

# Continue conversation in same thread
response2, thread_id, assistant_id = await process_with_assistant(
    user_message="What are the main functions?",
    thread_id=thread_id,
    assistant_id=assistant_id
)

# Low-level usage (for advanced control)
assistant_id = await create_or_get_assistant(
    name="Code Helper",
    instructions="You help with code",
    model="gpt-4o-mini",
    tools=[{"type": "file_search"}]
)

thread_id = await create_thread()

# Upload file separately
from backend.app.services.openai_files_api import upload_file_to_openai_api
file_id = await upload_file_to_openai_api(Path("doc.pdf"), purpose="assistants")

# Add message with file
msg_id = await add_message_to_thread(
    thread_id=thread_id,
    content="Analyze this document",
    file_ids=[file_id]
)

# Run and wait for completion
run = await run_assistant(thread_id, assistant_id)

# Get response
messages = await get_run_messages(thread_id)
```

**Real-World Example - Document Analysis Pipeline:**
```python
from backend.app.services.openai_assistant_service import process_with_assistant
from backend.app.services.openai_files_api import upload_file_to_openai_api
from pathlib import Path

async def analyze_project_documents(doc_paths: list[Path]):
    """Analyze multiple documents with persistent context"""
    
    # Upload all documents once
    file_ids = []
    for doc_path in doc_paths:
        file_id = await upload_file_to_openai_api(doc_path, purpose="assistants")
        file_ids.append(file_id)
    
    # Create assistant with file search
    assistant_id = await create_or_get_assistant(
        name="Documentation Analyzer",
        instructions="You analyze technical documentation and provide insights.",
        model="gpt-4o",
        tools=[{"type": "file_search"}]
    )
    
    # Create thread for conversation
    thread_id = await create_thread()
    
    # Add files to thread context
    await add_message_to_thread(
        thread_id=thread_id,
        content="I've uploaded project documentation. Ready to analyze.",
        file_ids=file_ids
    )
    
    # Interactive analysis
    questions = [
        "What is the overall architecture?",
        "What are the main APIs?",
        "What security measures are in place?"
    ]
    
    results = []
    for question in questions:
        # Continue conversation in same thread (context persists)
        response, _, _ = await process_with_assistant(
            user_message=question,
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        results.append({"question": question, "answer": response})
    
    return results

# Use the pipeline
doc_paths = [
    Path("docs/ARCHITECTURE.md"),
    Path("docs/API.md"),
    Path("docs/SECURITY.md")
]
analysis = await analyze_project_documents(doc_paths)
```

**API:**
- `create_or_get_assistant()` - Create or retrieve an assistant
- `create_thread()` - Create a conversation thread
- `get_thread()` - Retrieve thread details
- `add_message_to_thread()` - Add message with optional file attachments
- `run_assistant()` - Execute assistant and poll for completion
- `get_run_messages()` - Retrieve conversation messages
- `process_with_assistant()` - **High-level orchestration** (recommended entry point)

### Vector Lifecycle (`vector_lifecycle.py`)

Automated maintenance for the vector store.

**Features:**
- Detect and remove vectors for deleted files
- Detect and update vectors for modified files
- File hash tracking for change detection
- Dry-run mode for safe testing

**Usage:**
```python
from backend.app.services.vector_lifecycle import (
    perform_full_maintenance,
    remove_vectors_for_deleted_files,
    update_vectors_for_modified_files
)

# Full maintenance (cleanup + update)
results = perform_full_maintenance(dry_run=False)

# Cleanup only
cleanup_results = remove_vectors_for_deleted_files()

# Update only
update_results = update_vectors_for_modified_files()
```

**API:**
- `remove_vectors_for_deleted_files()` - Remove vectors for missing files
- `update_vectors_for_modified_files()` - Re-ingest modified files
- `perform_full_maintenance()` - Combined cleanup and update
- `calculate_file_hash()` - SHA256 hash for file content
- `get_all_vectorstore_sources()` - List all files in vector store

## Configuration

All services use centralized configuration from `backend/app/config.py`:

```python
# Vector store configuration
VECTORSTORE_PATH = "chroma_db"

# Ollama embeddings (local)
OLLAMA_EMBEDDING_MODEL = "mistral"
OLLAMA_BASE_URL = "http://localhost:11434"

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1"

# Document chunking
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
```

## Integration with Chat Orchestrator

The RAG service and file APIs are integrated into `langgraph_orchestrator.py`:

### RAG Integration
1. User sends message (with optional attachments)
2. Orchestrator retrieves query-based RAG context via CustomEnsembleRetriever
3. Context is stored in `state["rag_context"]`
4. LLM services use context to enrich prompts
5. Response is returned to user

### File Contextualization Strategy
**Decision logic in `_process_attached_files()` based on `target_llm`:**

- **OpenAI/Gemini**: Upload files via native APIs → reference by file_id in chat completion
- **Ollama**: Segment files → include content directly in prompt

**Key principle:** 
- Query-based RAG uses persistent vector stores (all LLMs)
- File attachments use optimized strategies per LLM (no temporary RAG collections)

## Testing

### Unit Tests - Services Module (90%+ Coverage)

**RAG and LLM Services (tests/unit/backend/services/)** - **NEW** - Comprehensive test suite for Issue #5
- `conftest.py` - Shared fixtures and mocks for service tests
  - Mock Ollama responses
  - Sample documents and retrievers
  - Configuration mocks
- `test_query_expander.py` (40+ tests) - Query expansion service with bilingual support
  - Successful query expansion scenarios
  - Error handling and fallback to original message
  - Term truncation and cleaning
  - Portuguese/English bilingual expansion
  - Context-aware expansion (future enhancement)
- `test_rag_postprocessor.py` (30+ tests) - RAG post-processing with local LLM
  - Context condensation with Ollama/Phi-3
  - Post-processing enable/disable logic
  - Error handling and fallback to raw context
  - Prompt template formatting
  - Large document set handling
- `test_rag_service.py` (30+ tests) - Main RAG service with ensemble retrieval
  - RAG disabled scenarios (no collections selected)
  - RAG enabled with collection filtering
  - Query expansion integration
  - Post-processing integration
  - Ensemble retriever functionality
  - Error handling and graceful degradation
  - Multiple collection support
- `test_llm_provider_interface_complete.py` (20+ tests) - LLM provider interface
  - Abstract method enforcement
  - Property validation
  - Error handling with LLMProviderError
  - verify_availability() variants
  - process_chat() contract compliance

**Other Service Tests**
- `tests/unit/backend/test_conversation_trace_service.py` - Conversation tracing service
- `tests/unit/backend/test_rag_service.py` - Legacy RAG tests (to be merged with new tests)
- `tests/unit/backend/test_openai_assistant_service.py` - Assistants API integration
- `tests/unit/backend/test_input_processor_segmentation.py` - File segmentation
- `tests/unit/test_vector_lifecycle.py` - Lifecycle management
- `tests/unit/backend/test_llm_provider_interface.py` - LLM provider factory and base class

### Integration Tests
- `tests/integration/test_openai_rag.py` - OpenAI + RAG integration
- `tests/integration/test_vector_maintenance.py` - Full maintenance workflow
- `tests/integration/backend/test_orchestrator_rag.py` - Orchestrator RAG flow

### Running Tests

**Run all service tests with coverage:**
```bash
# All service unit tests with coverage report
pytest tests/unit/backend/services/ --cov=app/services --cov-report=term-missing --cov-report=html -v

# Specific service test files
pytest tests/unit/backend/services/test_query_expander.py -v
pytest tests/unit/backend/services/test_rag_postprocessor.py -v
pytest tests/unit/backend/services/test_rag_service.py -v

# Coverage for specific services (target: 90%+)
pytest tests/unit/backend/services/ \
  --cov=app/services/query_expander_service \
  --cov=app/services/rag_postprocessor \
  --cov=app/services/rag/rag_service \
  --cov=app/services/llm_provider_interface \
  --cov-report=term-missing \
  --cov-report=json

# Integration tests
pytest tests/integration/backend/test_orchestrator_rag.py -v

# All tests (fast unit tests first)
pytest tests/unit/backend/ tests/integration/backend/ -v

# Watch mode (auto-rerun on changes)
pytest tests/unit/backend/services/ -v --looponfail
```

**Coverage Targets (Issue #5):**
- ✅ `query_expander_service.py`: 0% → 90%+ (40+ tests)
- ✅ `rag_postprocessor.py`: 0% → 90%+ (30+ tests)
- ✅ `rag/rag_service.py`: 56.74% → 90%+ (30+ tests)
- ✅ `llm_provider_interface.py`: 86.96% → 90%+ (20+ tests)

**Test Example - RAG Service:**
```python
# tests/unit/backend/test_rag_service.py
import pytest
from backend.app.services.rag_service import get_rag_service

@pytest.mark.asyncio
async def test_rag_retrieval_with_ensemble():
    """Test ensemble retrieval across multiple collections"""
    rag = get_rag_service(
        collection_names=['scareverse_docs', 'scareverse_code'],
        ensemble_weights=[0.6, 0.4]
    )
    
    message, docs, context = await rag.get_context(
        user_message="How do I create a cell?",
        session_id="test_session",
        k=5
    )
    
    assert len(docs) > 0
    assert len(context) > 0
    assert "cell" in context.lower()
```

## Compliance

This module follows project standards:

✅ **Modularization:** All files < 500 lines
  - conversation_trace_service.py: 252 lines
  - RAG module (modularized 2025-11-21):
    - rag/config.py: 35 lines
    - rag/embeddings.py: 69 lines
    - rag/retriever_manager.py: 244 lines
    - rag/rag_service.py: 388 lines
    - rag_service.py: 36 lines (backward compatibility shim)
  - openai_files_api.py: 225 lines
✅ **Documentation:** README present with comprehensive examples  
✅ **Tests:** Unit tests created, >90% coverage target  
✅ **Technical Naming:** English for all code  
✅ **Configuration:** Centralized in config.py  
✅ **BASE_DIR:** Used for all file paths  

## File Contextualization Architecture

### Query-based RAG (All LLMs)
```
User Query → CustomEnsembleRetriever → [docs, code, config] → RRF Merge → Context
```

### Attachment Handling (Updated)
```
OpenAI: File → Upload API → file_id → Assistants API Thread → Native Context
Gemini: File → Upload API → file_uri → Chat Completion (holistic)
Ollama: File → Segment → Direct Prompt Inclusion (segmented)
```

**OpenAI Migration:**
- **Old Approach**: File content injected into every prompt (inefficient, token-heavy)
- **New Approach**: Files uploaded once, referenced by `file_id` in Assistants API Threads
- **Benefits**: Reduced token usage, persistent context, native history management

## Future Enhancements

- [x] ~~Complete async file upload integration in orchestrator~~ **DONE** - Assistants API integration
- [x] ~~Add OpenAI file reference in chat completion~~ **DONE** - Assistants API with native file_id support
- [ ] Implement scheduled file cleanup mechanism for OpenAI Files API
- [ ] Add assistant/thread management UI in Cockpit
- [ ] Support additional embedding providers (Cohere, Vertex AI)
- [ ] Add caching for frequently accessed RAG contexts
- [ ] Implement file size limits and validation
- [ ] Add metrics and monitoring for RAG performance
- [ ] Add support for OpenAI Assistants API Tools (function calling)

## References

- [RULESET.md](../../../RULESET.md) - Project coding standards
- [ARQUITETURA_TESTES.md](../../../docs/ARQUITETURA_TESTES.md) - Testing architecture
- [RAG_INTEGRATION_SUMMARY.md](../../../RAG_INTEGRATION_SUMMARY.md) - RAG implementation overview
- [Issue #XXX](https://github.com/ScareCrowOrg/ScareVerseLab/issues/XXX) - Advanced RAG implementation
---

**Last Updated**: 2025-11-18  
**Services**: 5 core services (Conversation Trace, RAG, OpenAI Files, OpenAI Assistants, Vector Lifecycle)  
**Test Coverage**: 90%+ target

---

## Testing

### Test Coverage

Comprehensive unit tests are provided for critical service modules with high code coverage:

| Module | Coverage | Tests | Location |
|--------|----------|-------|----------|
| `openai_files_api.py` | 93% | 19 | `tests/unit/backend/services/test_openai_files.py` |
| `openai_assistant/` (all modules) | 96% | 40 | `tests/unit/backend/services/test_openai_assistant.py` |
| `vector_lifecycle.py` | 92% | 21 | `tests/unit/backend/services/test_vector_lifecycle.py` |
| `prompt_builder.py` | 85% | 34 | `tests/unit/backend/test_prompt_builder.py` |
| **Overall Services** | **91%** | **114** | - |

### Running Tests

To run all service tests:

```bash
# Run all service tests
cd backend
python3 -m pytest tests/unit/backend/services/ tests/unit/backend/test_prompt_builder.py -v

# Run specific service tests
python3 -m pytest tests/unit/backend/services/test_openai_files.py -v
python3 -m pytest tests/unit/backend/services/test_openai_assistant.py -v
python3 -m pytest tests/unit/backend/services/test_vector_lifecycle.py -v

# Run with coverage
python3 -m pytest --cov=app.services --cov-report=term-missing tests/unit/backend/services/
```

### Test Structure

**Mocking Utilities** (`tests/unit/backend/services/mocks/`)
- `openai_mock.py` - Reusable mocks for OpenAI API and HTTP client interactions
  - `MockHttpxAsyncClient` - Mock async HTTP client
  - `MockHttpxResponse` - Mock HTTP responses
  - Factory functions for creating mock OpenAI API responses

**Test Organization:**
- Unit tests focus on isolated functionality with mocked dependencies
- HTTP clients are mocked to avoid external API calls
- Vector store operations use mocked ChromaDB instances
- File operations use temporary files/directories
- All tests follow pytest conventions and include clear docstrings

### Key Test Features

1. **OpenAI API Mocking:**
   - All OpenAI API calls are mocked to avoid external dependencies
   - Comprehensive coverage of success and error scenarios
   - Timeout and HTTP error handling tested

2. **File Operations:**
   - Temporary files created and cleaned up automatically
   - Tests for upload, download, deletion
   - Error cases for missing files, invalid paths

3. **Vector Store Operations:**
   - Mocked ChromaDB vector store
   - Tests for file hash calculation
   - Deleted file cleanup validation
   - Modified file detection and re-ingestion

4. **Prompt Building:**
   - Tests for all provider formats (Ollama, Gemini, OpenAI)
   - Conversation history handling
   - RAG context integration
   - File attachment handling

### Test Compliance

All tests comply with RULESET.md requirements:
- **Rule 3.1**: Minimum 90% test coverage achieved (91% overall)
- **Rule 3.2**: Unit tests for business logic with proper mocking
- **Rule 3.3**: Fast execution (<2 minutes for unit tests)

