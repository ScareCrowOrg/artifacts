---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - providers
  - llm
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# LLM Provider Architecture

## Overview

This directory contains the polymorphic LLM provider architecture for ScareVerse. It implements a unified interface for all LLM services, eliminating code duplication and conditional logic in the router.

## Architecture Components

### 1. Base Interface (`llm_provider_interface.py`)

The `BaseLLMProvider` abstract base class defines the contract that all LLM providers must implement:

```python
from app.services.llm_provider_interface import BaseLLMProvider

class MyProvider(BaseLLMProvider):
    @property
    def provider_name(self) -> str:
        return "my_provider"
    
    @property
    def model_name(self) -> str:
        return "my_model_v1"
    
    async def process_chat(self, user_message, **kwargs):
        # Implementation
        return {"response": "..."}
```

### 2. Concrete Providers (`providers/`)

Each LLM service has its own provider implementation:

- **`OllamaProvider`**: Local Ollama instance integration
- **`GeminiProvider`**: Google Gemini API integration  
- **`OpenAIProvider`**: OpenAI API integration (Chat + Assistants)

### 3. Factory (`llm_provider_factory.py`)

The `LLMProviderFactory` manages provider instantiation using the singleton pattern:

```python
from app.services.llm_provider_factory import LLMProviderFactory

# Get default provider (singleton)
provider = LLMProviderFactory.get_provider("ollama")

# Get custom configured provider
provider = LLMProviderFactory.get_provider(
    "openai",
    model_id="gpt-4",
    api_key="sk-..."
)
```

## File Structure

```
services/
├── llm_provider_interface.py    # BaseLLMProvider ABC + LLMProviderError
├── llm_provider_factory.py      # Factory for provider instantiation
├── providers/
│   ├── __init__.py               # Provider exports
│   ├── ollama_provider.py        # Ollama implementation
│   ├── gemini_provider.py        # Gemini implementation
│   └── openai_provider.py        # OpenAI implementation
└── README.md                     # This file
```

## Handling Attached Content

Each provider handles `attached_content_metadata` differently:

### Ollama Provider
Extracts `segmented_content` and includes it directly in prompts:
```python
attached_content_metadata = [{
    "type": "segmented_content",
    "content": ["segment1", "segment2", "segment3"]
}]
```

### Gemini Provider
Extracts `file_id` and references files via Gemini Files API:
```python
attached_content_metadata = [{
    "type": "file_id",
    "id": "file_abc123"  # Already uploaded to Gemini Files API
}]
```

### OpenAI Provider
Uses file paths with Assistants API for holistic file management:
```python
attached_content_metadata = [{
    "type": "file_id",
    "id": "file_xyz",
    "path": "/tmp/tempfile.py"  # Path to temp file
}]
```

## Integration with Prompt Builder

All providers use the centralized `prompt_builder.py` service within their `process_chat()` implementation:

```python
from ..prompt_builder import PromptBuilder

builder = PromptBuilder(
    user_message=user_message,
    conversation_history=conversation_history,
    rag_context=rag_context,
    attached_content=segmented_content  # Provider-specific
)
prompt = builder.build_for_ollama()  # Or build_for_gemini/openai
```

## RAG Integration

All providers support RAG context retrieval:

1. **Pre-retrieved context**: Pass `rag_context` parameter
2. **Automatic retrieval**: Set `use_rag=True` (default)
3. **Collection filtering**: Use `selected_collections` parameter

```python
result = await provider.process_chat(
    user_message="Explain architecture",
    use_rag=True,
    selected_collections=["scareverse_docs", "scareverse_code"]
)
```

## Error Handling

All providers raise `LLMProviderError` for consistency:

```python
from app.services.llm_provider_interface import LLMProviderError

try:
    result = await provider.process_chat(user_message="Hello")
except LLMProviderError as e:
    logger.error(f"Provider error: {e}")
    # Handle error uniformly
```

## Adding New Providers

To add a new LLM provider:

1. Create a new file in `providers/` (e.g., `claude_provider.py`)
2. Implement `BaseLLMProvider` interface
3. Register in factory:

```python
from app.services.llm_provider_factory import LLMProviderFactory
from .providers.claude_provider import ClaudeProvider

LLMProviderFactory.register_provider("claude", ClaudeProvider)
```

4. Update `providers/__init__.py` to export the new provider

## Testing

Each provider should have:

- **Unit tests**: Test individual methods in isolation
- **Integration tests**: Test full chat flow with mocked APIs
- **Contract tests**: Verify BaseLLMProvider interface compliance

Example:
```python
import pytest
from app.services.providers import OllamaProvider

@pytest.mark.asyncio
async def test_ollama_process_chat():
    provider = OllamaProvider()
    result = await provider.process_chat(
        user_message="Hello",
        use_rag=False  # Disable for testing
    )
    assert "response" in result
```

## Configuration

Providers use centralized configuration from `config.py`:

- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`
- `GEMINI_API_KEY`, `GEMINI_DEFAULT_MODEL`, `GEMINI_TIMEOUT`
- `OPENAI_API_KEY`, `OPENAI_DEFAULT_MODEL`, `OPENAI_TIMEOUT`

Override at runtime via factory parameters:
```python
provider = LLMProviderFactory.get_provider(
    "ollama",
    model_id="llama2",
    base_url="http://custom:11434"
)
```

## Benefits

✅ **No conditional logic**: Router uses polymorphic dispatch  
✅ **Code reuse**: Shared prompt_builder and RAG integration  
✅ **Easy extensibility**: Add providers without modifying existing code  
✅ **Consistent interface**: All providers have the same API  
✅ **Better testability**: Mock providers easily for testing  
✅ **SOLID principles**: Complies with Open/Closed principle  

## Migration Notes

**Before** (chat_router.py):
```python
if modelo_provider == "ollama":
    from app.ollama_service import processar_chat_com_ollama_rag
    resposta = await processar_chat_com_ollama_rag(...)
elif modelo_provider == "gemini":
    from app.gemini_service import processar_chat_com_gemini_rag
    resposta = await processar_chat_com_gemini_rag(...)
elif modelo_provider == "openai":
    # More complex logic
    ...
```

**After** (chat_router.py):
```python
from app.services.llm_provider_factory import LLMProviderFactory

provider = LLMProviderFactory.get_provider(modelo_provider)
result = await provider.process_chat(
    user_message=request.intencao,
    conversation_history=historico_dicts,
    use_rag=True
)
resposta = result["response"]
```

## See Also

- `../prompt_builder.py` - Centralized prompt construction
- `../rag_service.py` - RAG context retrieval
- `../../routers/chat_router.py` - Router implementation
- `../../../tests/unit/backend/` - Unit tests
- `../../../tests/integration/backend/` - Integration tests
