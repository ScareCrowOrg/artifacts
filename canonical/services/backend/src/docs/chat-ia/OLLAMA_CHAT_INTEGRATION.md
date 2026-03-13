---
processed: true
processed_date: 2025-12-09
themes:
  - ollama
  - chat
  - conversation-history
  - ai-integration
modules:
  - backend
  - ai-integration
code_verified: true
dead_docs_found: false
---
# Ollama Chat Integration Documentation

## Overview

This document describes the Ollama integration for the ScareVerse chat system. The integration adds AI-powered conversational capabilities using a local Ollama instance, with support for contextual conversation history.

## Architecture

### Backend Components

#### 1. Ollama Service (`backend/app/ollama_service.py`)

The core service module that handles all Ollama interactions:

- **`montar_prompt_conversacional()`**: Builds contextual prompts
  - Keeps the last 5 complete messages
  - Minifies older messages to save tokens
  - Returns a formatted prompt string

- **`verificar_ollama_disponivel()`**: Health check for Ollama service
  - Async function that checks if Ollama is running
  - Returns `True` if available, `False` otherwise

- **`chamar_ollama()`**: Direct API call to Ollama
  - Sends prompts to the Ollama `/api/generate` endpoint
  - Handles timeouts and HTTP errors
  - Returns the generated response

- **`processar_chat_com_ollama()`**: High-level chat processing
  - Checks Ollama availability
  - Builds conversational prompt
  - Returns AI-generated response

#### 2. Updated Models (`backend/app/models.py`)

New model for conversation history:

```python
class MensagemChat(BaseModel):
    """Individual message in chat history."""
    role: Literal["user", "assistant"]
    content: str

class ProcessarIntencaoChatRequest(BaseModel):
    """Chat processing request."""
    intencao: str
    assignee_id: str
    historico: Optional[List[MensagemChat]] = None  # NEW
```

#### 3. Updated Endpoint (`backend/app/chat_router.py`)

The `/chat/processar` endpoint now:

1. Accepts optional conversation history
2. Attempts to use Ollama for AI responses
3. Falls back to keyword matching if Ollama unavailable
4. Maintains backward compatibility

### Frontend Components

#### Updated ChatIA Component (`cockpit-vue/src/components/ChatIA.vue`)

Changes to support conversation history:

```javascript
// Prepare conversation history (excluding current message)
const historico = this.messages
  .slice(0, -1)
  .map(msg => ({
    role: msg.role,
    content: msg.content
  }))

// Send with history
body: JSON.stringify({
  intencao: intencao,
  assignee_id: this.getUserId(),
  historico: historico  // NEW
})
```

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OLLAMA_TIMEOUT=30
```

### Available Models

The system defaults to `mistral`, but you can use any model installed in your Ollama instance:

- `mistral` (default)
- `llama2`
- `codellama`
- `llama3`
- `phi`
- etc.

## Setup Instructions

### 1. Install Ollama

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

**Windows:**
Download from https://ollama.com/download

### 2. Pull a Model

```bash
ollama pull mistral
```

### 3. Start Ollama

```bash
ollama serve
```

The service will start on `http://localhost:11434`

### 4. Configure Backend

Update your backend `.env`:

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OLLAMA_TIMEOUT=30
```

### 5. Start Backend

```bash
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 5051
```

### 6. Start Frontend

```bash
cd cockpit-vue
npm run dev
```

## API Usage

### Request Format

```json
POST /chat/processar
{
  "intencao": "Criar um sistema de login com JWT",
  "assignee_id": "user-uuid",
  "historico": [
    {
      "role": "user",
      "content": "Olá"
    },
    {
      "role": "assistant",
      "content": "Olá! Como posso ajudar?"
    },
    {
      "role": "user",
      "content": "Preciso criar um sistema de autenticação"
    }
  ]
}
```

### Response Format

```json
{
  "resposta": "Ótimo! Vou ajudá-lo a criar um sistema de login com JWT...",
  "celula": {
    "id": "celula-uuid",
    "tipo": "Executor de Scripts",
    "conteudo": "# Sistema de Login\n\n..."
  }
}
```

## Conversation Context Management

### How It Works

1. **Full History (≤ 5 messages)**: All messages included in prompt
2. **Long History (> 5 messages)**: 
   - Last 5 messages: Kept in full
   - Older messages: Minified to summary

### Example Prompt Building

**Input:**
```python
historico = [
  {"role": "user", "content": "Msg 1"},
  {"role": "assistant", "content": "Response 1"},
  # ... 6 more messages ...
  {"role": "user", "content": "Msg 8"}
]
intencao = "New message"
```

**Output:**
```
Histórico resumido: user: Msg 1 | assistant: Response 1 | user: Msg 2

user: Msg 4
assistant: Response 4
user: Msg 5
assistant: Response 5
user: Msg 6
assistant: Response 6
user: Msg 7
assistant: Response 7
user: Msg 8
user: New message
```

## Error Handling

### Ollama Unavailable

When Ollama is not available:

1. System logs a warning
2. Falls back to keyword-based cell creation
3. User still gets a functional response
4. No user-visible error

### Timeout Handling

- Default timeout: 30 seconds
- Configurable via `OLLAMA_TIMEOUT`
- Raises `httpx.TimeoutException` which is caught and logged

### HTTP Errors

- All HTTP errors are caught and logged
- System falls back to keyword matching
- Ensures continuous operation

## Testing

### Unit Tests

Run the unit tests:

```bash
cd backend
python3 tests/test_ollama_integration.py
```

Expected output:
```
============================================================
  OLLAMA INTEGRATION TESTS
============================================================

=== Test: Prompt without history ===
✓ PASS: Prompt without history works correctly

=== Test: Prompt with short history ===
✓ PASS: Prompt with short history works correctly

=== Test: Prompt with long history ===
✓ PASS: Prompt with long history works correctly

... (more tests)

============================================================
  RESULTS: 5 passed, 0 failed
============================================================
```

### Manual Testing

1. Start Ollama: `ollama serve`
2. Start backend: `uvicorn app.main:app`
3. Open frontend: `http://localhost:3000`
4. Use the chat interface
5. Observe AI-powered responses

### Testing Without Ollama

The system gracefully degrades:

1. Stop Ollama: `pkill ollama`
2. Use chat interface
3. System uses keyword-based responses
4. Functionality maintained

## Performance Considerations

### Token Usage

- Conversation history is automatically managed
- Last 5 messages kept in full
- Older messages minified
- Reduces token consumption

### Response Time

- Typical Ollama response: 2-10 seconds
- Depends on:
  - Model size
  - Prompt length
  - Hardware (GPU vs CPU)
  - Conversation context

### Recommendations

- Use smaller models (mistral, phi) for faster responses
- Consider GPU acceleration for production
- Monitor timeout settings based on your hardware

## Future Enhancements

### Planned Features

1. **Session Persistence**: Save conversation history to database
2. **Model Selection**: Allow users to choose models
3. **Streaming Responses**: Real-time token streaming
4. **Context Window Management**: Smarter history compression
5. **Multi-turn Planning**: Enhanced task decomposition
6. **Asset Generation**: Integration with ScareVerse assets

### Integration Points

- **Books/Cells**: Reference existing content in prompts

- **Code Execution**: Direct code execution from AI responses

## Troubleshooting

### Ollama Not Responding

**Symptom**: Chat responses are slow or use keyword matching

**Solution**:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
pkill ollama
ollama serve
```

### Model Not Found

**Symptom**: Error "model not found"

**Solution**:
```bash
# Pull the model
ollama pull mistral

# List available models
ollama list
```

### Port Conflicts

**Symptom**: Ollama won't start on 11434

**Solution**:
```bash
# Use a different port
OLLAMA_HOST=0.0.0.0:11435 ollama serve

# Update backend .env
OLLAMA_BASE_URL=http://localhost:11435
```

### Memory Issues

**Symptom**: Ollama crashes or is very slow

**Solution**:
- Use smaller models (mistral-7b instead of llama2-70b)
- Reduce concurrent requests
- Add more RAM or use GPU acceleration

## References

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Ollama API Reference](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [ScareVerse Project Documentation](ScareVerse_Project.md)
- [Current Implementation README](../IMPLEMENTATION_OVERVIEW.md)

## Support

For issues or questions:
1. Check this documentation
2. Review the troubleshooting section
3. Check backend logs: `backend/logs/`
4. Open an issue on GitHub
