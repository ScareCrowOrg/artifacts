---
processed: true
processed_date: 2025-12-09
themes:
  - ai
  - chat
  - documentation
  - index
  - llm
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Chat IA Documentation

Complete documentation for the AI chat integration in ScareVerse, covering multiple providers, intention classification, and orchestration.

## Index

### Quick Start Guides
- `QUICK_START_CHAT_IA.md` - Quick start guide for chat IA integration
- `QUICK_START_OLLAMA.md` - Quick start for Ollama local models

### Implementation Guides
- `CHAT_IA_INTEGRATION.md` - Core chat IA integration documentation
- `OLLAMA_CHAT_INTEGRATION.md` - Ollama provider integration
- `LANGCHAIN_LANGGRAPH_IMPLEMENTATION.md` - LangChain and LangGraph implementation
- `GEMINI_FILES_API.md` - Google Gemini Files API for efficient file handling

### Feature Summaries
- `IMPLEMENTATION_SUMMARY_OLLAMA.md` - Ollama implementation summary
- `IMPLEMENTATION_SUMMARY_MODEL_SELECTION.md` - Model selection implementation
- `IMPLEMENTATION_SUMMARY_ORCHESTRATION.md` - Orchestration implementation summary
- `CHAT_IA_IMPROVEMENTS_2025_11.md` - Recent improvements (November 2025)

### User Guides
- `MODEL_SELECTION_GUIDE.md` - Guide for selecting and configuring AI models

## Overview

The Chat IA system provides:
- Multi-provider AI chat (Ollama, Gemini)
- Intention classification
- Conversation orchestration
- File attachment support
- Context-aware responses
- Model switching

## Supported Providers

### Ollama (Local Models)
Run AI models locally for privacy and speed:
- Llama 2, Mistral, CodeLlama, Phi-2
- No API costs
- Full data privacy
- Offline capability

See [OLLAMA_CHAT_INTEGRATION.md](./OLLAMA_CHAT_INTEGRATION.md) and [QUICK_START_OLLAMA.md](./QUICK_START_OLLAMA.md).

### Google Gemini (Cloud Models)
Access Google's latest AI models:
- Gemini Pro, Gemini Pro Vision
- Advanced reasoning capabilities
- File attachment support via Gemini Files API
- Token-efficient file handling

See [GEMINI_FILES_API.md](./GEMINI_FILES_API.md) for efficient file processing.

## Key Features

### Intention Classification
Automatically classifies user messages:
- Code generation requests
- Documentation queries
- File operations
- General conversation
- System commands

Enables intelligent routing and context-aware responses.

### Conversation Orchestration
LangGraph-based workflow orchestration:
- Multi-step conversations
- State management
- Tool calling
- Error recovery
- Context retention

See [LANGCHAIN_LANGGRAPH_IMPLEMENTATION.md](./LANGCHAIN_LANGGRAPH_IMPLEMENTATION.md).

### File Attachments
Attach files to chat messages:
- Upload files for analysis
- Reference code files
- Process documents
- Gemini Files API for efficient token usage

See [GEMINI_FILES_API.md](./GEMINI_FILES_API.md) for implementation details.

### Model Selection
Dynamic model selection:
- Switch between providers
- Choose specific models
- Configure model parameters
- Per-conversation settings

See [MODEL_SELECTION_GUIDE.md](./MODEL_SELECTION_GUIDE.md).

## API Endpoints

### Chat Processing
- `POST /api/chat/processar` - Process chat message
  - Body: `{ message, session_id, model_id, attachments }`
  - Returns: `{ response, intention, model_used }`

### Model Management
- `GET /api/modelos-ia/` - List available AI models
- `POST /api/modelos-ia/` - Register new model
- `GET /api/modelos-ia/{id}` - Get model details
- `PUT /api/modelos-ia/{id}` - Update model configuration
- `DELETE /api/modelos-ia/{id}` - Delete model

### Service Management
- `GET /api/services/status` - Check service availability
- `POST /api/services/ollama/start` - Start Ollama service
- `POST /api/services/ollama/stop` - Stop Ollama service

## Usage Examples

### Basic Chat
```python
import requests

response = requests.post('http://localhost:8000/api/chat/processar', json={
    'message': 'Explique o que é FastAPI',
    'session_id': 'user-session-123',
    'model_id': 'gemini-pro'
})

result = response.json()
print(f"Response: {result['response']}")
print(f"Intention: {result['intention']}")
```

### Chat with File Attachment
```python
response = requests.post('http://localhost:8000/api/chat/processar', json={
    'message': 'Analise este código',
    'session_id': 'user-session-123',
    'model_id': 'gemini-pro',
    'attachments': ['path/to/file.py']
})
```

### Direct Conversation Mode
```python
# Bypass intention classification for direct conversation
response = requests.post('http://localhost:8000/api/chat/processar', json={
    'message': 'Como você está?',
    'session_id': 'user-session-123',
    'model_id': 'ollama-llama2',
    'mode': 'direct'
})
```

## Configuration

### Ollama Setup
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models
ollama pull llama2
ollama pull mistral
ollama pull codellama

# Start Ollama service
ollama serve
```

### Gemini Setup
```bash
# Add to .env
GEMINI_API_KEY=your_api_key_here

# Enable Files API
GEMINI_FILES_ENABLED=true
```

### Environment Variables
```bash
# Provider Configuration
OLLAMA_BASE_URL=http://localhost:11434
GEMINI_API_KEY=your_api_key

# Chat Settings
DEFAULT_CHAT_MODEL=gemini-pro
ENABLE_INTENTION_CLASSIFIER=true
MAX_CONVERSATION_HISTORY=50

# File Handling
MAX_ATTACHMENT_SIZE_MB=10
GEMINI_FILES_ENABLED=true
```

## Recent Improvements

Recent updates documented in [CHAT_IA_IMPROVEMENTS_2025_11.md](./CHAT_IA_IMPROVEMENTS_2025_11.md):
- Enhanced Gemini Files API integration
- Improved intention classification accuracy
- Better error handling and recovery
- Optimized token usage
- Direct conversation mode
- Model switching improvements

## Testing

### Unit Tests
```bash
# Test chat processing logic
pytest tests/unit/test_chat.py

# Test intention classifier
pytest tests/unit/test_intention_classifier.py

# Test providers
pytest tests/unit/test_ollama_service.py
pytest tests/unit/test_gemini_service.py
```

### Integration Tests
```bash
# Test complete chat flow
pytest tests/integration/test_chat_integration.py

# Test with real providers (requires setup)
pytest tests/integration/test_chat_providers.py
```

## Troubleshooting

### Common Issues

**Ollama not connecting**
- Check if Ollama service is running: `ollama serve`
- Verify `OLLAMA_BASE_URL` in `.env`
- Ensure firewall allows localhost connections

**Gemini API errors**
- Verify API key is valid
- Check quota limits in Google Cloud Console
- Ensure network connectivity

**File attachment failures**
- Check file size limits
- Verify file permissions
- Ensure Gemini Files API is enabled

**Slow responses**
- Use smaller models for faster responses
- Enable caching for repeated queries
- Consider using Ollama for local processing

## Performance Optimization

### Token Efficiency
- Use Gemini Files API for large files
- Implement conversation summarization
- Limit context window size
- Cache common responses

### Response Speed
- Use Ollama for code generation (faster)
- Stream responses for better UX
- Implement response caching
- Optimize model selection

## Related Documentation

- [Backend App Code](../../app/) - Chat implementation
- [API Documentation](../api/) - API endpoint details
- [Test Architecture](../../../docs/ARQUITETURA_TESTES.md) - Testing strategy
- [Frontend Chat Components](../../../cockpit-vue/src/components/) - Chat UI

## Notes

- Technical names (endpoints, parameters) use English
- Documentation may be bilingual
- Keep conversation history under 50 messages
- Monitor API usage and costs
- Regular model updates recommended
- Follow responsible AI practices
