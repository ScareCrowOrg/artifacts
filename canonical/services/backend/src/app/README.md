---
processed: true
processed_date: 2025-12-08
themes:
  - backend
  - api
  - structure
  - overview
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Backend Application Core

Core application modules of the ScareVerse backend, implementing the FastAPI application, routers, services, and business logic.

## Directory Structure

```
backend/app/
├── main.py                     # FastAPI application entry point
├── config.py                   # Application configuration
├── __init__.py                 # Package initialization
│
├── routers/                    # API Endpoints (15 routers)
│   ├── README.md               # Router documentation
│   ├── auth_router.py          # Authentication endpoints
│   ├── celulas_router.py       # Cell management endpoints
│   ├── chat_router.py          # AI chat processing
│   ├── config_router.py        # Configuration management
│   ├── file_ops_router.py      # File operations
│   ├── issues_router.py        # GitHub issues integration
│   ├── issues_dashboard_router.py  # Issues dashboard
│   ├── livros_router.py        # Book management
│   ├── modelos_ia_router.py    # AI model management
│   ├── ngrok_router.py         # Public file sharing
│   ├── router.py               # Main router (legacy)
│   ├── services_router.py      # External services
│   ├── sessoes_router.py       # Session management
│   ├── system_router.py        # System information
│   └── usuarios_router.py      # User management
│
├── models/                     # Data Models
│   ├── README.md               # Models documentation
│   ├── content.py              # NotebookItem models (Celula, Livro, NotebookItemType)
│   ├── adapters.py             # Adapter pattern implementations
│   ├── interfaces.py           # Interface definitions
│   ├── base.py                 # Base models and enums
│   ├── users.py                # User models
│   ├── agents.py               # Agent models
│   ├── artifacts.py            # Artifact models
│   ├── chat.py                 # Chat models
│   ├── sessions.py             # Session models
│   ├── auth.py                 # Authentication models
│   ├── ai_models.py            # AI model configuration
│   └── oauth_config.py         # OAuth configuration
│
├── services/                   # Business Logic Services
│   ├── README.md               # Services documentation
│   ├── rag_service.py          # RAG operations
│   ├── vector_lifecycle.py     # Vector store lifecycle
│   └── openai_files_api.py     # OpenAI Files API
│
├── core/                       # Core Components
│   ├── README.md               # Core documentation
│   └── models.py               # Core data models
│
├── database/                   # Database Layer
│   ├── README.md               # Database documentation
│   ├── connection.py           # DB connections
│   ├── operations.py           # DB operations
│   ├── config_ops.py           # Config operations
│   ├── encryption.py           # DB encryption
│   └── database_router.py      # DB endpoints
│
├── orchestrator/               # Workflow Orchestration
│   ├── README.md               # Orchestrator documentation
│   ├── core.py                 # Core orchestration
│   ├── instance.py             # Orchestrator instance
│   ├── state.py                # State management
│   ├── helpers.py              # Helper functions
│   └── file_processing.py      # File processing
│
├── workflows/                  # LangGraph Workflows
│   ├── README.md               # Workflows documentation
│   ├── ingestion_graph.py      # Document ingestion workflow
│   ├── preprocess_and_chunk.py # Preprocessing workflow
│   └── generate_embeddings_and_store.py  # Embedding workflow
│
├── file_processors/            # File Processing
│   ├── README.md               # File processors documentation
│   ├── content_minimizer.py   # Content minimization
│   ├── file_segmenter.py       # File segmentation
│   ├── message_builder.py      # Message building
│   └── token_counter.py        # Token counting
│
├── utils/                      # Utility Functions
│   ├── README.md               # Utils documentation
│   ├── chat_history_manager.py # Chat history
│   ├── conversation_memory.py  # Conversation memory
│   ├── document_ingestion.py   # Document ingestion
│   └── input_processor.py      # Input processing
│
├── scripts/                    # Maintenance Scripts
│   ├── README.md               # Scripts documentation
│   ├── seed_data.py            # Database seeding
│   ├── import_json_to_tinydb.py # JSON import
│   ├── dump_tinydb_contents.py # DB dump
│   ├── dump_refs_soft.py       # Reference dump
│   └── refs_soft_loader.py     # Reference loader
│
├── auth.py                     # Authentication logic
├── crypto_utils.py             # Cryptographic utilities
├── database.py                 # MongoDB connection (legacy)
├── models.py                   # Data models (to be split)
├── tree_builder.py             # File tree builder
│
├── gemini_service.py           # Google Gemini API
├── openai_service.py           # OpenAI API
├── ollama_service.py           # Ollama API
├── intention_classifier.py     # Intention classification
├── langchain_tools.py          # LangChain utilities
├── langgraph_orchestrator.py   # LangGraph orchestrator
├── document_tools.py           # Document tools
├── openai_file_processor.py    # OpenAI file processor
├── workflow_executor.py        # Workflow executor
├── event_bus.py                # Event bus
├── file_utils.py               # File utilities
├── tinydb_database.py          # TinyDB operations
└── orchestrator.py             # Orchestrator (legacy)
```

## Index

### New Architecture: NotebookItemType (v2.0)
**Type-Driven Notebook Items with Dynamic Workflow Loading**

The ScareVerse backend now implements a sophisticated type system for notebook items (cells and books) that enables:
- **Type-Driven Behavior**: Cells and books inherit default configurations from their types
- **Dynamic Workflow Loading**: Workflows loaded at runtime using `importlib` (no hardcoded imports)
- **Instance-Level Overrides**: Configurable per-type policy for allowing overrides
- **Backward Compatibility**: Full compatibility with legacy `tipoCelulaId` field

**Key Components:**
- `models/content.py` - `NotebookItemType` model with `default_refs` and `default_initial_data`
- `models/adapters.py` - Enhanced `NotebookItemAdapter` with dynamic workflow resolution
- `routers/celulas_router.py`, `routers/livros_router.py` - Type-aware creation endpoints
- `scripts/migrate_notebook_item_types.py` - Migration script from `TipoCelula`

**Documentation:**
- [Architecture Guide](../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md) - Complete architecture documentation with diagrams and examples
- [Migration Guide](../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md#migration) - How to migrate existing types
- [Unit Tests](../../tests/unit/backend/) - Comprehensive test coverage (59 test cases)

**Workflow Resolution Priority:**
1. Instance `refs["workflow_graph"]` (if `allow_instance_override_refs=True`)
2. Type `default_refs["workflow_graph"]` (fallback or enforced)
3. No workflow (execution skipped)

### Main Application
- `main.py` - FastAPI application entry point and configuration
- `config.py` - Application configuration and environment variables
- `__init__.py` - Package initialization

### Authentication & Security
- `auth.py` - Authentication logic and OAuth2 integration
- `crypto_utils.py` - Cryptographic utilities for secure operations
- [README_CRYPTO.md](./README_CRYPTO.md) - Detailed cryptography documentation

### API Routers (in `routers/` directory)
See [routers/README.md](./routers/README.md) for complete router documentation.
- All API endpoints organized by domain
- 15 routers covering authentication, content, files, system, and more
- Follows RESTful conventions with Pydantic validation

### Data Models (in `models/` directory)
See [models/README.md](./models/README.md) for models documentation.
- `models.py` - Data models (Pydantic schemas) - *to be split into modules*
- Request/response models for all endpoints
- Database schemas and validation

### Business Logic Services (in `services/` directory)
See [services/README.md](./services/README.md) for services documentation.
- RAG (Retrieval Augmented Generation) operations
- Vector store lifecycle management
- OpenAI Files API integration

### Data & Persistence
- `database.py` - MongoDB connection and operations (legacy)
- `database/` - Complete database layer with operations, encryption, and router
- `tree_builder.py` - File tree builder for artifact navigation
- `tinydb_database.py` - TinyDB operations for local storage

### AI Services
- `gemini_service.py` - Google Gemini API integration (Files API, no RAG)
- `openai_service.py` - OpenAI API integration with mandatory RAG support
- `ollama_service.py` - Ollama local models integration with mandatory RAG support
- `intention_classifier.py` - User intention classification
- `langchain_tools.py` - LangChain utilities and tools
- `langgraph_orchestrator.py` - LangGraph workflow orchestration
- `document_tools.py` - Document reading tools for function calling

### Workflows & Orchestration
- `orchestrator/` - Workflow orchestration engine
- `workflows/` - LangGraph workflow definitions
- `workflow_executor.py` - Workflow execution engine
- `event_bus.py` - Event-driven communication

### File Processing
- `file_processors/` - File processing modules
- `file_utils.py` - File utility functions
- `openai_file_processor.py` - OpenAI file processing

### Utilities
- `utils/` - Utility functions organized by domain

### Maintenance Scripts (in `scripts/` directory)
See [scripts/README.md](./scripts/README.md) for scripts documentation.
- Database seeding and migration
- Data import/export utilities
- Debugging and maintenance tools

### RAG (Retrieval Augmented Generation)
The backend implements **mandatory RAG integration** for OpenAI and Ollama:

#### RAG-Enabled Services
- **OpenAI**: `processar_chat_com_openai_rag` - Always retrieves context from vector store
- **Ollama**: `processar_chat_com_ollama_rag` - Always retrieves context from vector store
- **Gemini**: Uses Google Files API directly, **NO RAG** (operates on files without vectorization)

#### How RAG Works
**RAG is ALWAYS active for OpenAI and Ollama, regardless of attachments:**
- **Without attachments**: General RAG search based on user message, retrieving relevant context from the entire vector store
- **With attachments**: RAG search prioritizes the attached files, but still searches the vector store for additional context

Attachments are **NOT injected as raw text** into prompts. Instead, they are used to **prioritize** which documents the RAG system should focus on during context retrieval.

#### RAG Features
- **Priority-based context retrieval**: Attached files > File references > General search
- **Vector store**: ChromaDB with Ollama embeddings (local) or OpenAI embeddings (API)
- **Context enrichment**: Retrieved documents injected into system prompts
- **Fallback handling**: Gracefully handles missing vector store or RAG errors
- **Token optimization**: Only relevant context added to prompts

#### RAG Service (`services/rag_service.py`)
- Centralized RAG operations with multiple embedding providers
- Lazy-loaded vector stores for performance
- Configurable context retrieval (default: k=5 documents)
- Automatic context formatting for LLM prompts

See [backend/docs/ARQUITETURA_TESTES.md](../docs/ARQUITETURA_TESTES.md) for RAG testing strategy.

### AI Function Calling
The backend implements OpenAI Function Calling for large document support:
- **read_local_document** - Tool for reading local documents on-demand
- **processar_com_function_calling** - Function calling loop with up to 5 iterations
- **Security**: Path traversal prevention, directory whitelist, file size limits
- See [backend/docs/FUNCTION_CALLING.md](../docs/FUNCTION_CALLING.md) for detailed documentation

### Utilities
- `utils/` - Utility functions organized by domain

### Maintenance Scripts (in `scripts/` directory)
See [scripts/README.md](./scripts/README.md) for scripts documentation.
- Database seeding and migration
- Data import/export utilities
- Debugging and maintenance tools

## Migration Guide

### Import Path Changes

The directory reorganization changes import paths for routers and scripts. Update your code as follows:

#### Router Imports
**Old (before refactoring):**
```python
from app.celulas_router import celulas_router
from app.chat_router import chat_router
from app.file_ops_router import file_ops_router
```

**New (after refactoring):**
```python
from app.routers.celulas_router import celulas_router
from app.routers.chat_router import chat_router
from app.routers.file_ops_router import file_ops_router
```

#### Script Imports
**Old:**
```python
from app.seed_data import init_seed_data
from app.refs_soft_loader import load_refs
```

**New:**
```python
from app.scripts.seed_data import init_seed_data
from app.scripts.refs_soft_loader import load_refs
```

### What Stayed the Same

✅ Main application imports unchanged:
- `from app.config import ...`
- `from app.models import ...`
- `from app.database import ...`
- `from app.auth import ...`

✅ Service imports unchanged:
- `from app.services.rag_service import ...`
- `from app.orchestrator.core import ...`
- `from app.workflows.ingestion_graph import ...`

✅ All API endpoints remain the same
✅ Database schemas and models unchanged
✅ No breaking changes to external integrations

### Running the Application

```bash
# From backend directory - still works the same
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing After Migration

```bash
# Run all unit tests
pytest tests/unit/backend/ -v

# Run integration tests
pytest tests/integration/backend/ -v

# Run specific router tests
pytest tests/endpoints/backend/test_celulas_router.py -v
```

## ⚠️ SECURITY WARNING - FILE OPERATIONS (LOCAL DEVELOPMENT ONLY)

**IMPORTANT**: The file operations module (`file_ops_router.py` and `utils.py`) has been configured to allow **UNRESTRICTED file operations** for local development agility.

### What This Means
- **ANY file extension** can be read, written, or deleted within `BASE_DIR`
- No restrictions on file types (`.exe`, `.bin`, `.dll`, etc.)
- Full control over the local repository filesystem

### Security Measures Still Active
✅ **Path traversal protection** - Cannot escape `BASE_DIR`  
✅ **OS permission validation** - Respects filesystem permissions  
✅ **Null byte injection prevention** - Blocks malicious path inputs  
✅ **Boundary enforcement** - All operations confined to repository root  

### Why This Configuration?
This setup prioritizes **development speed** and **flexibility** for:
- Quick file editing via cockpit interface
- AI-assisted repository manipulation
- Rapid prototyping without extension restrictions

### Risks Accepted
⚠️ Possibility of accidental deletion of critical files  
⚠️ Potential modification of system-level configs within repo  
⚠️ Binary file operations might cause corruption  
⚠️ No audit trail beyond git history  

### Requirements for Safe Use
- ✅ **Local environment only** (not exposed to network)
- ✅ **Version control active** (git protects against data loss)
- ✅ **Single user** (no multi-user concerns)
- ✅ **Conscious usage** (user understands risks)

### Future Considerations
When moving to production or multi-user environments:
1. Re-enable extension whitelist in `utils.py`
2. Add audit logging for file operations
3. Implement role-based access control
4. Consider read-only mode for sensitive directories
5. Add backup/versioning beyond git

**DO NOT deploy this configuration to production or network-accessible environments.**

---

## Architecture

### Router Structure
All routers follow FastAPI conventions:
- RESTful endpoints with proper HTTP methods
- Request/response validation using Pydantic models
- Authentication middleware for protected endpoints
- Error handling and logging

### Service Layer
Services encapsulate business logic and external integrations:
- AI services (Gemini, Ollama) handle model communication
- Database service manages MongoDB operations
- File operations maintain artifact persistence

### Configuration
Configuration follows centralized pattern:
- Environment variables via `.env` file
- `BASE_DIR` for path references (see [backend/docs/BASE_DIR_GUIDELINES.md](../docs/BASE_DIR_GUIDELINES.md))
- Type-safe config using Pydantic settings

## Usage

### Running the Application

```bash
# From backend directory
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Environment Configuration

Required environment variables:
- `MONGODB_URI` - MongoDB connection string
- `GOOGLE_CLIENT_ID` - OAuth2 client ID
- `GOOGLE_CLIENT_SECRET` - OAuth2 client secret
- `JWT_SECRET_KEY` - JWT signing key
- `GEMINI_API_KEY` - Google Gemini API key (optional)

See `.env.example` in project root for complete list.

## Testing

Test coverage: **85%** (target: 90%)

Run tests:
```bash
pytest tests/unit/
pytest tests/integration/
```

See [backend/tests/README.md](../tests/README.md) for detailed test documentation.

## Related Documentation

- [Backend Documentation](../docs/) - Complete backend documentation
- [API Documentation](../docs/api/) - API endpoint details
- [Authentication Guide](../docs/auth/) - OAuth2 and JWT authentication
- [Chat IA Documentation](../docs/chat-ia/) - AI chat integration
- [Base Directory Guidelines](../docs/BASE_DIR_GUIDELINES.md) - File path conventions
- [Test Architecture](../../docs/ARQUITETURA_TESTES.md) - Testing strategy

## Notes

- All technical names (functions, parameters, endpoints) use English
- Documentation and comments may be in Portuguese
- Follow modularization guidelines: files should not exceed 500 lines
- Maintain test coverage above 90% for new code
