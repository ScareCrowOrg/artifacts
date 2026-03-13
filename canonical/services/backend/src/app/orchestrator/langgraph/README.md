---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - orchestrator
  - langgraph
  - ai
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# LangGraph Orchestrator Module

## Overview

This module provides LangGraph-based orchestration for the ScareVerse chat system. It implements a state machine that processes user messages through multiple stages: instruction reception, intention classification, action execution, response generation, and chat history management.

## Architecture

The orchestrator uses a **LangGraph StateGraph** to manage the flow of chat interactions:

```
┌─────────────────┐
│ RecebeInstrucao │  ← Entry point
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│ ClassificaIntencao  │  ← Classify user intention
└────────┬────────────┘
         │
         ├──────────────┐
         ▼              ▼
┌──────────────┐  ┌────────────────┐
│ ExecutaAcao  │  │ RetornaResposta│
└──────┬───────┘  └────────┬───────┘
       │                   │
       └──────────┬────────┘
                  ▼
        ┌───────────────────┐
        │ ManageChatHistory │
        └─────────┬─────────┘
                  ▼
                 END
```

## Module Structure

### Core Files

- **`langgraph_chat_flow.py`** (268 lines) - Main orchestrator class and graph construction
- **`langgraph_state.py`** (38 lines) - State type definition
- **`instruction_receiver.py`** (165 lines) - Entry node: receives and prepares instructions
- **`intention_classifier_node.py`** (42 lines) - Classifies user intentions
- **`action_executor.py`** (104 lines) - Executes actions (create/execute cells)
- **`response_generator.py`** (195 lines) - Generates contextual responses
- **`history_manager.py`** (130 lines) - Manages chat history and summarization
- **`file_processor.py`** (162 lines) - Processes attached files by LLM type
- **`function_calling.py`** (97 lines) - OpenAI function calling support
- **`__init__.py`** (26 lines) - Public API exports

**Total Lines**: ~1,227 lines → Modularized from original 839 lines (includes new features)

## Public API

### Primary Class

```python
from app.orchestrator.langgraph import ChatOrchestrator, get_orchestrator

# Get global instance (recommended)
orchestrator = get_orchestrator()

# Or create new instance
orchestrator = ChatOrchestrator()
```

### Processing Messages

#### Synchronous Processing

```python
result = orchestrator.process(
    mensagem="Crie uma célula para sistema de login",
    responsavel_id="user123",
    modelo="mistral",
    historico=[
        {"role": "user", "content": "Olá"},
        {"role": "assistant", "content": "Olá! Como posso ajudar?"}
    ],
    use_rag=True,  # Enable RAG context retrieval
    use_memory=True,
    session_id="session_abc",
    target_llm="ollama",  # Specify target LLM provider
    attached_files=[  # Optional: attach files for processing
        {"path": "/tmp/doc.txt", "type": "text/plain"}
    ]
)

print(result["resposta"])
print(result["intencao"])  # CRIAR, EXECUTAR, CONVERSAR, etc.
```

#### Asynchronous Processing (with Function Calling)

```python
result = await orchestrator.process_async(
    mensagem="Analise o arquivo docs/README.md",
    responsavel_id="user123",
    modelo="gpt-4o",
    enable_function_calling=True,
    use_rag=True,
    use_memory=True,
    session_id="session_abc",
    target_llm="openai"  # Specify OpenAI for function calling
)
```

### State Management

The orchestrator maintains state throughout the graph execution:

```python
from app.orchestrator.langgraph import OrchestratorState

# State includes:
# - mensagem: User's message
# - historico: Conversation history
# - intencao: Classified intention (CRIAR, EXECUTAR, CONVERSAR, etc.)
# - acao_realizada: Whether action was executed
# - resultado_acao: Action result
# - celula_criada: Created cell data
# - rag_context: Retrieved RAG documents
# - session_id: Session for memory management
# - use_memory: Enable conversational memory
# - attached_files: Files from UI
# - current_chat_summary: LLM-generated summary
# - recent_chat_history: Last N turns
```

## Features

### 1. Intention Classification

Automatically classifies user intentions:
- **CONVERSAR**: General conversation
- **CRIAR**: Create new cell
- **EXECUTAR**: Execute existing cell
- **REFLETIR**: Reflect on results
- **DEPURAR**: Debug issues

### 2. RAG Context Retrieval

Retrieves relevant documents from vector store with intelligent prioritization:

```python
orchestrator.process(
    mensagem="Explain the architecture in #docs/README.md",
    responsavel_id="user123",
    use_rag=True,  # Enable RAG - now unified across all LLM providers
    session_id="session_123",
    target_llm="ollama"  # Works with ollama, openai, gemini
)
```

**Key Features:**
- **Three-Tier Prioritization System**:
  1. **Priority 1**: Attached files (processed separately)
  2. **Priority 2**: File references using `#filepath` syntax (top-3 chunks per file)
  3. **Priority 3**: General RAG search across collections (k=5 per collection)
- Unified RAG activation via `use_rag` flag
- Works consistently across Ollama, OpenAI, and Gemini
- Automatic context retrieval from pre-indexed collections
- Intelligent deduplication of results
- Most relevant context appears first

**File Reference Syntax:**
Use `#filepath` in your message to prioritize specific documents:
```python
orchestrator.process(
    mensagem="What's in #config/settings.py and #docs/API.md?",
    use_rag=True,
    target_llm="ollama"
)
# Will prioritize content from those specific files
```

### 3. Conversational Memory

Maintains conversation history across sessions:

```python
orchestrator.process(
    mensagem="Continue onde paramos",
    responsavel_id="user123",
    use_memory=True,  # Enable memory
    session_id="session_123"
)
```

### 4. Chat History Summarization

Automatically summarizes long conversations:
- Triggers after N turns or token limit
- Uses OpenAI for consistent summaries
- Preserves recent context while compressing old history

**New: Explicit History Usage Instructions**
- LLM prompts now include clear instructions that history is for reference only
- Prevents question repetition and confusion about current user intent
- Consistent implementation across all LLM providers (Gemini, OpenAI, Ollama)
- History is clearly separated from the current question with section markers

### 5. File Attachment Processing

Unified file processing based on target LLM capabilities:

**Strategy per LLM:**
- **OpenAI**: Upload to Files API → Returns `file_id` for Assistants API
- **Gemini**: Upload to Files API → Returns `file_uri` for fileData
- **Ollama**: Segment content → Store in state for prompt inclusion

```python
orchestrator.process(
    mensagem="Analyze this code",
    responsavel_id="user123",
    attached_files=[
        {"path": "/tmp/code.py", "type": "text/x-python"}
    ],
    target_llm="openai"  # Automatically uses correct upload strategy
)
```

**Key Improvements:**
- All file uploads centralized in `file_processor.py`
- Async uploads for OpenAI and Gemini
- Automatic file segmentation for Ollama
- Proper error handling and fallbacks
- Eliminates duplicate upload logic from router

### 6. Function Calling (OpenAI)

Enables on-demand document access:

```python
result = await orchestrator.process_async(
    mensagem="Read the docs/API.md file",
    responsavel_id="user123",
    modelo="gpt-4o",
    enable_function_calling=True
)
```

## Recent Changes & Improvements

### November 2025 Updates
- ✅ **BUGFIX: Node Name Consistency**: Fixed critical node routing issue where CRIAR/EXECUTAR intentions failed
- ✅ **Intelligent LLM Response Generation**: LLM now synthesizes answers from RAG context instead of appending raw text
- ✅ **Three-Tier RAG Prioritization**: Attached files → Referenced files (`#filepath`) → General search
- ✅ **RAG and File Processing Unification**: Centralized file handling across all LLM providers
- ✅ **Comprehensive Testing**: 25+ new tests with 95%+ pass rate
- ✅ **Improved History Usage Instructions**: Explicit instructions to LLMs about how to use conversation history
  - Prevents question repetition and confusion about user intent
  - Consistent implementation across Gemini, OpenAI, and Ollama services
  - Comprehensive test coverage with 18+ unit tests

📚 **Detailed Changelog**: See [docs/recent-changes.md](./docs/recent-changes.md) for:
- Complete problem statements and solutions
- Before/after code examples
- Performance improvements
- Breaking changes and migration guides
- Feature timeline

## Graph Nodes

The orchestrator consists of 5 main nodes that work together to process user requests:

1. **RecebeInstrucao** - Entry point with intelligent RAG orchestration
2. **ClassificaIntencao** - Classifies user intention (CRIAR, EXECUTAR, CONVERSAR, etc.)
3. **ExecutaAcao** - Executes actions (creates/executes cells)
4. **RetornaResposta** - Generates intelligent, context-aware responses
5. **ManageChatHistory** - Manages conversation history and summarization

📚 **Detailed Node Documentation**: See [docs/node-documentation.md](./docs/node-documentation.md) for comprehensive information about each node, including:
- Detailed responsibilities and logic
- State fields modified
- Code examples
- Performance considerations
- Error handling strategies

## Dependencies

This module depends on:

### Internal Dependencies
- `app.intention_classifier` - Intention classification
- `app.langchain_tools` - Cell tools
- `app.openai_service` - OpenAI integration
- `app.document_tools` - Document access tools
- `app.services.rag_service` - RAG service
- `app.utils.conversation_memory` - Memory management
- `app.utils.chat_history_manager` - History utilities
- `app.utils.input_processor` - Input processing

### External Dependencies
- `langgraph` - State graph framework
- `langchain-core` - LangChain core components

## Testing

### Test Structure
- **Unit Tests**: Individual node testing (`tests/unit/backend/orchestrator/`)
- **Integration Tests**: Full graph execution (`tests/integration/backend/test_orchestrator*.py`)
- **E2E Tests**: Complete user workflows (`tests/e2e/backend/`)

### Running Tests
```bash
# All orchestrator tests
pytest tests/unit/backend/orchestrator/ -v

# Integration tests
pytest tests/integration/backend/test_orchestrator_rag.py -v

# With coverage (90%+ target)
pytest tests/unit/backend/orchestrator/ \
  --cov=backend/app/orchestrator/langgraph \
  --cov-report=html
```

📚 **Comprehensive Testing Guide**: See [docs/testing-guide.md](./docs/testing-guide.md) for:
- Detailed testing strategies
- Code examples for unit/integration/E2E tests
- Mocking external services
- Test fixtures and best practices
- Coverage goals and debugging techniques

## Future Enhancements

Planned improvements:
- [ ] Sophisticated cell ID extraction from natural language
- [ ] Streaming response support
- [ ] Multi-turn action sequences
- [ ] Advanced RAG strategies (re-ranking, fusion)
- [ ] Assistant/thread management UI
- [ ] Scheduled file cleanup for OpenAI/Gemini APIs

## Documentation Index

- **[Main README](./README.md)** - This file (overview and quick start)
- **[Node Documentation](./docs/node-documentation.md)** - Detailed node information
- **[Recent Changes](./docs/recent-changes.md)** - Changelog and migration guides
- **[Testing Guide](./docs/testing-guide.md)** - Comprehensive testing strategies

## References

- **[RULESET.md](../../../../RULESET.md)** - Project modularization rules
- **[LangGraph Documentation](https://langchain-ai.github.io/langgraph/)** - LangGraph framework
- **[LangChain Documentation](https://python.langchain.com/)** - LangChain components

## Questions?

For questions or issues:
- Review documentation files listed above
- Check [RULESET.md](../../../../RULESET.md) for coding standards
- Open an issue with tag `orchestrator`

---

**Last Updated**: 2025-11-15  
**Version**: 3.0 (Modularized with intelligent RAG)  
**Files**: 11 Python modules + 4 documentation files
