---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - langgraph
  - architecture
  - nodes
  - api-reference
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# LangGraph Orchestrator - Node Documentation

This document provides detailed documentation for each node in the LangGraph state machine.

## Graph Nodes Overview

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

## Node 1: RecebeInstrucao (`instruction_receiver.py`)

**Purpose**: Entry point that prepares the request with intelligent RAG orchestration

**Key Responsibilities:**
- Initializes state fields
- Loads conversation memory
- Processes attached files (Priority 1)
- **Retrieves RAG context with prioritization** (NEW):
  - **Priority 2**: Extracts file references from message using `#filepath` syntax
  - Processes referenced files to get relevant chunks
  - **Priority 3**: Supplements with general RAG search if needed (< 3 priority docs)
  - Deduplicates results
  - Most relevant context appears first

**RAG Prioritization Logic:**
```
User message: "Explain #docs/README.md and overall architecture"
         ↓
1. Extract file references → ["docs/README.md"]
2. Get top-3 chunks from referenced file
3. Check if sufficient (threshold: 3 docs)
4. If not, perform general RAG search
5. Combine results (priority docs first)
6. Deduplicate by content preview
         ↓
Final rag_context: [doc1_from_readme, doc2_from_readme, doc3_from_readme, 
                    doc4_general, doc5_general]
```

**State Fields Modified:**
- `mensagem` - User's message (initialized)
- `historico` - Conversation history (loaded from memory)
- `attached_files` - File attachments (processed by LLM type)
- `rag_context` - Retrieved RAG documents (prioritized)
- `session_id` - Session identifier
- `use_memory` - Memory flag
- `use_rag` - RAG flag

**File Processing by LLM Type:**
- **OpenAI**: Upload to Files API → Returns `file_id` for Assistants API
- **Gemini**: Upload to Files API → Returns `file_uri` for fileData
- **Ollama**: Segment content → Store in state for prompt inclusion

**Usage Example:**
```python
from app.orchestrator.langgraph import OrchestratorState
from app.orchestrator.langgraph.instruction_receiver import recebe_instrucao

state = {
    "mensagem": "Explain #docs/API.md",
    "responsavel_id": "user123",
    "modelo": "mistral",
    "use_rag": True,
    "use_memory": True,
    "session_id": "session_abc",
    "target_llm": "ollama",
    "attached_files": [{"path": "/tmp/doc.txt", "type": "text/plain"}]
}

# Execute node (async)
result_state = await recebe_instrucao(state)

# Check results
print(result_state["rag_context"])  # Prioritized documents
print(result_state["attached_files"])  # Processed files
```

## Node 2: ClassificaIntencao (`intention_classifier_node.py`)

**Purpose**: Classifies user intention to route to appropriate action

**Key Responsibilities:**
- Uses IntentionClassifier to analyze user message
- Routes to appropriate action based on intention
- Supports multiple intention types

**Intention Types:**
- **CONVERSAR**: General conversation
- **CRIAR**: Create new cell
- **EXECUTAR**: Execute existing cell
- **REFLETIR**: Reflect on results
- **DEPURAR**: Debug issues

**State Fields Modified:**
- `intencao` - Classified intention (CRIAR, EXECUTAR, CONVERSAR, etc.)

**Routing Logic:**
```python
if intencao in ["CRIAR", "EXECUTAR"]:
    next_node = "ExecutaAcao"
else:
    next_node = "RetornaResposta"
```

**Usage Example:**
```python
from app.orchestrator.langgraph.intention_classifier_node import classifica_intencao

state = {
    "mensagem": "Crie uma célula para sistema de login",
    "historico": [],
    # ... other fields
}

result_state = classifica_intencao(state)
print(result_state["intencao"])  # "CRIAR"
```

## Node 3: ExecutaAcao (`action_executor.py`)

**Purpose**: Executes actions based on classified intention

**Key Responsibilities:**
- Creates cells (CRIAR intention)
- Executes cells (EXECUTAR intention)
- Validates action results

**State Fields Modified:**
- `acao_realizada` - Whether action was executed (bool)
- `resultado_acao` - Action result (dict or string)
- `celula_criada` - Created cell data (for CRIAR)

**CRIAR Flow:**
```
1. Parse cell parameters from message
2. Call cell creation service
3. Store cell data in state
4. Set acao_realizada = True
```

**EXECUTAR Flow:**
```
1. Extract cell ID from message
2. Load cell data from database
3. Execute cell code
4. Store execution result in state
5. Set acao_realizada = True
```

**Usage Example:**
```python
from app.orchestrator.langgraph.action_executor import executa_acao

state = {
    "mensagem": "Crie uma célula",
    "intencao": "CRIAR",
    "responsavel_id": "user123",
    # ... other fields
}

result_state = executa_acao(state)
assert result_state["acao_realizada"] is True
print(result_state["celula_criada"])  # Cell data
```

## Node 4: RetornaResposta (`response_generator.py`)

**Purpose**: Generates intelligent, context-aware responses

**Key Responsibilities:**
- **CONVERSAR Intention**: Invokes LLM to synthesize response from RAG context
  - Builds system prompt with RAG context
  - Calls appropriate LLM service (Gemini, OpenAI, or Ollama)
  - Instructs LLM to use ONLY provided context
  - Fallback to static response on error
- Includes RAG information when available
- Saves to memory if enabled

**Intelligent Response Generation** (NEW):
For CONVERSAR intention, the response generator now:
1. Formats RAG context into readable prompt
2. Constructs system prompt instructing LLM to use context
3. Calls the appropriate LLM service (based on `target_llm`)
4. Returns synthesized, intelligent response

**Example Before & After:**

*Before (appending raw context)*:
```
User: "Explain the architecture"
Assistant: "Olá! Sou o assistente...
📚 Contexto dos Documentos:
--- Document 1 ---
The architecture uses LangGraph...
--- Document 2 ---
RAG is used to retrieve..."
```

*After (synthesized response)*:
```
User: "Explain the architecture"
Assistant: "Based on the documentation, ScareVerse uses LangGraph for 
workflow orchestration and RAG for context retrieval from the knowledge base.
The system follows a modular architecture with separate components for..."
```

**State Fields Modified:**
- `resposta` - Final response to user (string)

**LLM Selection Logic:**
```python
if target_llm == "openai":
    response = await openai_service.chat(prompt, model)
elif target_llm == "gemini":
    response = await gemini_service.chat(prompt, model)
else:  # ollama
    response = ollama_service.chat(prompt, model)
```

**Usage Example:**
```python
from app.orchestrator.langgraph.response_generator import retorna_resposta

state = {
    "mensagem": "Explain the architecture",
    "intencao": "CONVERSAR",
    "rag_context": [...],  # Retrieved documents
    "target_llm": "ollama",
    "modelo": "mistral",
    # ... other fields
}

result_state = await retorna_resposta(state)
print(result_state["resposta"])  # Intelligent, synthesized response
```

## Node 5: ManageChatHistory (`history_manager.py`)

**Purpose**: Manages conversation history and triggers summarization

**Key Responsibilities:**
- Updates recent history with new turn
- Triggers summarization when needed (N turns or token limit)
- Compresses old conversations
- Preserves recent context

**Summarization Strategy:**
- Uses OpenAI for consistent summaries
- Triggers after configurable threshold (default: 10 turns)
- Keeps last N turns as "recent_chat_history"
- Compresses older history into "current_chat_summary"

**State Fields Modified:**
- `recent_chat_history` - Last N turns (list)
- `current_chat_summary` - LLM-generated summary (string)

**Usage Example:**
```python
from app.orchestrator.langgraph.history_manager import manage_chat_history

state = {
    "mensagem": "Continue onde paramos",
    "resposta": "Vamos continuar...",
    "recent_chat_history": [...],  # Last 10 turns
    "use_memory": True,
    "session_id": "session_abc",
    # ... other fields
}

result_state = manage_chat_history(state)
# History updated, summarization triggered if needed
```

## Integration Between Nodes

The nodes work together in a pipeline:

```
User Message
    ↓
RecebeInstrucao (loads memory, processes files, retrieves RAG)
    ↓
ClassificaIntencao (determines user intent)
    ↓
    ├─→ ExecutaAcao (if CRIAR/EXECUTAR)
    │       ↓
    └─→ RetornaResposta (synthesizes response)
            ↓
    ManageChatHistory (updates memory, summarizes if needed)
            ↓
        Response to User
```

## State Management

The orchestrator maintains comprehensive state throughout execution:

```python
from app.orchestrator.langgraph import OrchestratorState

# State includes:
state = {
    # Input
    "mensagem": str,              # User's message
    "responsavel_id": str,        # User ID
    "modelo": str,                # Model name
    "historico": List[Dict],      # Conversation history
    
    # Configuration
    "use_rag": bool,              # Enable RAG context retrieval
    "use_memory": bool,           # Enable conversational memory
    "session_id": str,            # Session for memory management
    "target_llm": str,            # LLM provider (ollama, openai, gemini)
    
    # Classification
    "intencao": str,              # CRIAR, EXECUTAR, CONVERSAR, etc.
    
    # Action
    "acao_realizada": bool,       # Whether action was executed
    "resultado_acao": Any,        # Action result
    "celula_criada": Dict,        # Created cell data
    
    # RAG
    "rag_context": List[Document],  # Retrieved RAG documents
    
    # Files
    "attached_files": List[Dict],   # Files from UI
    
    # Memory
    "current_chat_summary": str,    # LLM-generated summary
    "recent_chat_history": List[Dict],  # Last N turns
    
    # Output
    "resposta": str,              # Final response to user
}
```

## Performance Considerations

- **Average processing time**: 100-500ms (without LLM calls)
- **With RAG retrieval**: +200-400ms
- **With function calling**: +500-2000ms (depends on document size)
- **With file uploads**: +500-1500ms (OpenAI/Gemini async uploads)

## Error Handling

All nodes implement graceful error handling:
- Logs errors with full context
- Continues processing when possible
- Returns meaningful error messages
- Preserves state for debugging

**Example Error Handling:**
```python
try:
    # Node logic
    result = execute_action(state)
except Exception as e:
    logger.error(f"Error in node: {e}", exc_info=True)
    state["error"] = str(e)
    # Continue with fallback behavior
    return state
```

## Testing Nodes

Each node can be tested in isolation:

```python
# Unit test example
from app.orchestrator.langgraph.action_executor import executa_acao

def test_criar_celula():
    state = {
        "mensagem": "Crie uma célula",
        "intencao": "CRIAR",
        "responsavel_id": "user123",
    }
    
    result = executa_acao(state)
    
    assert result["acao_realizada"] is True
    assert "celula_criada" in result
```

## References

- [Main README](../README.md) - Orchestrator overview
- [Recent Changes Documentation](./recent-changes.md) - Detailed changelog
- [Testing Guide](./testing-guide.md) - Testing strategies
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)

---

**Last Updated**: 2025-11-15  
**Nodes**: 5 nodes (RecebeInstrucao, ClassificaIntencao, ExecutaAcao, RetornaResposta, ManageChatHistory)
