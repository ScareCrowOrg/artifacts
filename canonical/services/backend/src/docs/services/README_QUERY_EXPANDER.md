---
processed: true
processed_date: 2025-12-08
themes:
  - rag
  - search
  - nlp
  - bilingual
  - ai-integration
modules:
  - backend
  - services
code_verified: true
dead_docs_found: false
---
# Query Expander Service

## Overview

The Query Expander Service enhances RAG (Retrieval Augmented Generation) vector search by generating expanded queries with bilingual terms using a local Phi-3 LLM. This improves search relevance for the ScareVerse bilingual project (Portuguese/English).

## Purpose

In a bilingual codebase, direct vector search with user prompts may miss relevant documents due to language barriers. This service addresses this by:

1. **Bilingual Term Generation**: Generates equivalent terms in both Portuguese and English
2. **Synonym Expansion**: Includes relevant synonyms and related concepts
3. **Improved Search Recall**: Increases chances of finding relevant documents across languages

## Architecture

```
User Query → Query Expander (Phi-3) → Expanded Query → Vector Search → Results
              ↓ (on error)
         Original Query (Fallback)
```

## Components

### `query_expander_service.py`

**Main Functions:**

- `generate_expanded_query(user_message, model, max_terms)`: Generates expanded bilingual query
- `generate_expanded_query_with_context(user_message, conversation_history, model)`: Context-aware expansion (future feature)

**Key Features:**

- Uses Phi-3 LLM via `chamar_ollama()` from `ollama_service.py`
- Generates 5-10 search terms (configurable)
- Includes both Portuguese and English terms
- Graceful error handling with fallback to original query
- Term limit enforcement to prevent overly long queries

## Integration with RAG Service

The query expander is integrated into `rag_service.py` at the `get_context()` method:

```python
# In rag_service.py
async def get_context(
    self,
    user_message: str,
    enable_query_expansion: Optional[bool] = True,  # ← New parameter
    ...
):
    # Step 1: Expand query if enabled
    if enable_query_expansion:
        expanded_query = await generate_expanded_query(user_message)
        search_query = expanded_query
    else:
        search_query = user_message
    
    # Step 2: Use expanded query for retrieval
    context_docs = ensemble_retriever.get_relevant_documents(search_query)
```

## Usage Examples

### Basic Usage

```python
from app.services.query_expander_service import generate_expanded_query

# Portuguese query
expanded = await generate_expanded_query("Como criar uma célula?")
# Result: "célula, cell, criar, create, novo, new, item, notebook, estrutura, structure"

# English query
expanded = await generate_expanded_query("How to create a cell?")
# Result: "cell, célula, create, criar, new, novo, item, notebook, structure, estrutura"
```

### With RAG Service

```python
from app.services.rag_service import RAGService

rag = RAGService(collection_names=['scareverse_docs'])

# With query expansion (default)
msg, docs, context = await rag.get_context(
    user_message="Como funciona a autenticação?",
    selected_collections=['scareverse_docs'],
    enable_query_expansion=True  # Generates bilingual terms
)

# Without query expansion
msg, docs, context = await rag.get_context(
    user_message="How does authentication work?",
    selected_collections=['scareverse_docs'],
    enable_query_expansion=False  # Uses original query
)
```

## Configuration

### Environment Variables

The query expander uses configuration from `config.py`:

- `OLLAMA_BASE_URL`: Ollama API endpoint (default: http://localhost:11434)
- `OLLAMA_TIMEOUT`: Request timeout in seconds (default: 30)

### Module Constants

In `query_expander_service.py`:

- `DEFAULT_EXPANSION_MODEL`: Default LLM model (default: "phi3:latest")
- `MAX_EXPANDED_TERMS`: Maximum number of terms to generate (default: 10)
- `QUERY_EXPANSION_PROMPT_TEMPLATE`: Prompt template for Phi-3

## Prompt Engineering

The prompt template instructs Phi-3 to:

1. Analyze the user's question
2. Generate 5-10 relevant keywords
3. Include synonyms and related terms
4. Provide Portuguese and English equivalents
5. Format as comma-separated list

**Example Prompt:**
```
You are a query expansion assistant specialized in bilingual (Portuguese/English) term generation.

Your task: Given a user's question, generate 5-10 relevant search terms including:
1. Key concepts from the original question
2. Synonyms and related terms
3. Portuguese and English equivalents for all terms
4. Technical terms if applicable

User Question: "Como criar uma célula?"

Expanded Search Terms: célula, cell, criar, create, novo, new, item, notebook
```

## Error Handling

The service implements robust error handling:

1. **Ollama Connection Errors**: Falls back to original query
2. **Empty Responses**: Falls back to original query
3. **Timeouts**: Falls back to original query (with warning log)
4. **Invalid Responses**: Cleans and uses partial results or falls back

All errors are logged with appropriate severity levels.

## Performance Considerations

### Latency

- **Query Expansion Time**: ~100-500ms (local Phi-3)
- **Total RAG Time**: +10-20% overhead
- **Acceptable for User Experience**: Yes (sub-second response)

### Optimization

- Local LLM (Phi-3) minimizes network latency
- Term limit prevents excessive token generation
- Async implementation for non-blocking operation
- Fallback ensures service continuity

## Testing

### Unit Tests (`test_query_expander_service.py`)

- 16 tests covering:
  - Bilingual term generation (PT → EN, EN → PT)
  - Error handling and fallbacks
  - Term limit enforcement
  - Custom model support
  - Prompt template validation

### Integration Tests (`test_rag_query_expansion.py`)

- 6 tests covering:
  - End-to-end RAG flow with expansion
  - Enable/disable toggle
  - Error fallback scenarios
  - Bilingual input handling

**Test Coverage:** 100% passing (22 tests total)

## Monitoring and Logging

The service logs:

- Query expansion requests (INFO)
- Generated expanded queries (DEBUG)
- Expansion errors (ERROR)
- Fallback events (WARNING)
- Performance metrics (number of terms, character count)

**Example Logs:**
```
INFO: Generating expanded query for: 'Como criar uma célula?...'
DEBUG: Calling Phi-3 with model: phi3:latest
INFO: Query expansion successful: 8 terms generated (57 chars)
DEBUG: Expanded query: célula, cell, criar, create, novo, new, item, notebook
```

## Future Enhancements

1. **Context-Aware Expansion**: Use conversation history to improve term selection
2. **Cache Frequent Expansions**: Cache common query expansions in Redis
3. **A/B Testing**: Compare results with/without expansion
4. **Adaptive Expansion**: Dynamically adjust number of terms based on query complexity
5. **Multi-Language Support**: Extend beyond PT/EN to other languages

## Dependencies

- `ollama_service.py`: For LLM integration
- `langchain`: For embeddings and vector store
- `pytest`, `pytest-asyncio`: For testing
- Phi-3 LLM: Local model via Ollama

## References

- Issue: [Melhorar Busca Vetorial: Geração de Query Expandida com LLM (Phi-3)](link-to-issue)
- RAG Service: `backend/app/services/rag_service.py`
- Ollama Service: `backend/app/ollama_service.py`
- Tests: `tests/unit/backend/test_query_expander_service.py`
