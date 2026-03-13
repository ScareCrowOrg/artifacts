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
# OpenAI Service Module

## Overview

The `openai_service` module provides comprehensive integration with OpenAI's API, supporting multiple patterns: standard chat, function calling, RAG-enhanced chat, and Assistants API integration.

## Architecture

The module is organized into specialized components:

```
app/openai_service/
├── __init__.py           # Public API exports (47 lines)
├── api_client.py         # Core API client (126 lines)
├── chat_processor.py     # Standard chat processing (117 lines)
├── function_calling.py   # Function calling support (237 lines)
├── rag_integration.py    # RAG integration (177 lines)
├── assistants.py         # Assistants API + RAG (186 lines)
└── README.md            # This file
```

## Components

### API Client (api_client.py)

Core HTTP client for OpenAI API with error handling.

**Key Functions:**
- `chamar_openai(payload, api_key, base_url, timeout)` - Make API calls
- `verificar_openai_disponivel(api_key, base_url)` - Check API availability

### Chat Processor (chat_processor.py)

Standard chat processing with conversation history management.

**Key Functions:**
- `processar_chat_com_openai(...)` - Process chat with history and attachments

### Function Calling (function_calling.py)

Implements OpenAI function calling pattern (tool execution loop).

**Key Functions:**
- `processar_com_function_calling(messages, tools, tool_executor, ...)` - LLM → tools → LLM loop

### RAG Integration (rag_integration.py)

RAG-enhanced chat with vector store context retrieval.

**Key Functions:**
- `processar_chat_com_openai_rag(...)` - Chat with mandatory RAG context

### Assistants API (assistants.py)

OpenAI Assistants API integration with RAG enrichment.

**Key Functions:**
- `processar_chat_com_openai_assistants(...)` - Assistants API with RAG + threads

## Usage

### Basic Chat

```python
from app.openai_service import processar_chat_com_openai

response = await processar_chat_com_openai(
    nova_intencao="What is Python?",
    historico=[
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"}
    ],
    api_key="sk-...",
    temperature=0.7
)
print(response)
```

### Function Calling

```python
from app.openai_service import processar_com_function_calling

def my_tool_executor(tool_name, arguments):
    if tool_name == "get_weather":
        return f"Weather for {arguments.get('city')}: Sunny, 72°F"
    return "Unknown tool"

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"]
        }
    }
}]

messages = [{"role": "user", "content": "What's the weather in Paris?"}]

result = await processar_com_function_calling(
    messages=messages,
    tools=tools,
    tool_executor=my_tool_executor,
    api_key="sk-..."
)

print(result["response"])  # "The weather in Paris is Sunny, 72°F"
print(result["tool_calls_made"])  # [{"tool": "get_weather", ...}]
```

### RAG-Enhanced Chat

```python
from app.openai_service import processar_chat_com_openai_rag

# RAG automatically retrieves context from vector store
response = await processar_chat_com_openai_rag(
    nova_intencao="Explain the ScareVerse architecture",
    api_key="sk-...",
    use_rag=True  # Default
)
print(response)
```

### Assistants API with RAG

```python
from app.openai_service import processar_chat_com_openai_assistants

result = await processar_chat_com_openai_assistants(
    nova_intencao="Help me debug this code",
    attached_files=[{"path": "/path/main.py", "type": "text/plain"}],
    api_key="sk-...",
    use_rag=True,
    selected_collections=["scareverse_code"]
)

print(result["response"])
print(f"Thread ID: {result['thread_id']}")  # For conversation continuity
```

## Configuration

The module uses configuration from `app/config.py`:

```python
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1")
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "60.0"))
OPENAI_DEFAULT_MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4")
```

**Environment Variables:**
- `OPENAI_API_KEY` - OpenAI API key (required)
- `OPENAI_API_URL` - API base URL (default: official OpenAI API)
- `OPENAI_TIMEOUT` - Request timeout in seconds (default: 60)
- `OPENAI_DEFAULT_MODEL` - Default model ID (default: gpt-4)

## Function Calling Pattern

The function calling module implements the OpenAI tool execution loop:

1. **Send messages + tools** to OpenAI
2. **Check response**: Tool call requested?
   - Yes → Execute tools, add results to messages, goto step 1
   - No → Return final response
3. **Repeat** until final response or max iterations

Example tool definition:

```python
{
    "type": "function",
    "function": {
        "name": "search_documentation",
        "description": "Search the ScareVerse documentation",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        }
    }
}
```

## RAG Integration

RAG (Retrieval-Augmented Generation) enhances responses with relevant context:

1. **Retrieve** relevant chunks from vector store based on user message
2. **Format** context with metadata (file paths, chunk info)
3. **Inject** context into system prompt
4. **Call** OpenAI with enriched prompt

RAG is **always enabled** by default in `processar_chat_com_openai_rag` and `processar_chat_com_openai_assistants`.

## Error Handling

All functions handle errors consistently:

- `ValueError` - Missing API key configuration
- `RuntimeError` - API errors, timeouts, network issues
- Detailed logging of all errors

Example:

```python
try:
    response = await processar_chat_com_openai(
        nova_intencao="Hello",
        api_key="invalid-key"
    )
except ValueError as e:
    print(f"Configuration error: {e}")
except RuntimeError as e:
    print(f"API error: {e}")
```

## Dependencies

- `httpx` - Async HTTP client
- `app.config` - Configuration management
- `app.services.prompt_builder` - Centralized prompt building
- `app.services.rag_service` - RAG context retrieval
- `app.services.openai_assistant_service` - Assistants API implementation

## Testing

Tests for this module are located in:
- `tests/unit/backend/services/test_openai_*.py` - Unit tests
- `tests/integration/backend/services/test_openai_integration.py` - Integration tests

Run tests:
```bash
pytest tests/unit/backend/services/test_openai_*.py -v
```

## File Size Compliance

All files in this module are under 500 lines (Rule 1.1):
- `api_client.py`: 126 lines ✅
- `chat_processor.py`: 117 lines ✅
- `function_calling.py`: 237 lines ✅
- `rag_integration.py`: 177 lines ✅
- `assistants.py`: 186 lines ✅
- `__init__.py`: 47 lines ✅

**Total:** 890 lines across 6 modules (previously 727 lines in 1 file)

## Migration Guide

### Before (Monolithic)

```python
from app.openai_service import (
    processar_chat_com_openai,
    processar_com_function_calling
)

response = await processar_chat_com_openai(...)
```

### After (Modularized)

```python
# Public API remains the same - no code changes needed!
from app.openai_service import (
    processar_chat_com_openai,
    processar_com_function_calling
)

response = await processar_chat_com_openai(...)
```

The modularization is **fully backward compatible**. All existing code continues to work without modification.

## Internal Module Access (Advanced)

If you need direct access to specialized modules:

```python
from app.openai_service.api_client import chamar_openai
from app.openai_service.chat_processor import processar_chat_com_openai
from app.openai_service.function_calling import processar_com_function_calling
from app.openai_service.rag_integration import processar_chat_com_openai_rag
from app.openai_service.assistants import processar_chat_com_openai_assistants

# Direct module usage (advanced)
response_data = await chamar_openai(payload={"model": "gpt-4", ...})
```

## Performance Considerations

- **Timeouts**: Default 60s, configurable via `timeout` parameter
- **Retry Logic**: Not implemented (caller responsibility)
- **Rate Limiting**: Not implemented (OpenAI handles this)
- **Token Counting**: Not implemented (consider adding for cost tracking)

## Future Enhancements

- Add streaming support for real-time responses
- Implement token counting and cost tracking
- Add retry logic with exponential backoff
- Support for parallel tool calls
- Caching layer for repeated queries
- Metrics and observability

## References

- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Function Calling Guide](https://platform.openai.com/docs/guides/function-calling)
- [Assistants API Guide](https://platform.openai.com/docs/assistants/overview)
- [RULESET.md](../../RULESET.md) - Project rules
- [services/rag_service.py](../services/rag_service.py) - RAG implementation
