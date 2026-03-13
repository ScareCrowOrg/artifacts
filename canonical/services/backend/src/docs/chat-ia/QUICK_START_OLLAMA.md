---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - ai
  - ollama
  - quickstart
modules:
  - backend
  - ai-integration
code_verified: true
dead_docs_found: false
---
# Quick Start: Ollama Chat Integration

## 5-Minute Setup

### 1. Install Ollama (One-time)

**Linux/macOS:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from https://ollama.com/download

### 2. Pull the Model

```bash
ollama pull mistral
```

### 3. Start Ollama

```bash
ollama serve
```

Leave this terminal open. Ollama will run on http://localhost:11434

### 4. Configure Backend

Create or update `backend/.env`:

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OLLAMA_TIMEOUT=30
```

### 5. Start the Backend

```bash
cd backend
pip3 install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 5051
```

### 6. Start the Frontend

```bash
cd cockpit-vue
npm install
npm run dev
```

### 7. Use the Chat!

Open the frontend and start chatting. Your conversations will now be powered by Ollama AI!

## Testing Without Ollama

The system works without Ollama too! If Ollama is not running, it automatically falls back to keyword-based responses.

## Verify It's Working

### Check Ollama Status
```bash
curl http://localhost:11434/api/tags
```

Should return a list of installed models.

### Check Backend Logs
Look for:
```
INFO: Ollama respondeu com sucesso - Response length: XXX chars
```

### In the Chat
Ask complex questions - if you get contextual, detailed responses, Ollama is working!

## Troubleshooting

### "Ollama não disponível"
**Fix**: Start Ollama with `ollama serve`

### "Model not found"
**Fix**: `ollama pull mistral`

### Slow Responses
**Fix**: Use a smaller model or enable GPU acceleration

## What Was Implemented?

✅ **Conversational Context**: Maintains last 5 messages, minifies older ones
✅ **Smart Prompts**: AI receives full conversation context
✅ **Graceful Fallback**: Works with or without Ollama
✅ **Configurable**: Change model, timeout, etc. via .env
✅ **Production-Ready**: Fully tested and secure

## More Information

- **Complete Guide**: See `OLLAMA_CHAT_INTEGRATION.md`
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY_OLLAMA.md`
- **Code**: `backend/app/ollama_service.py`
- **Tests**: `backend/tests/test_ollama_integration.py`

## Quick Commands

```bash
# Start Ollama
ollama serve

# List models
ollama list

# Pull new model
ollama pull llama2

# Check status
curl http://localhost:11434/api/tags

# Run tests
cd backend && python3 tests/test_ollama_integration.py
```

## Configuration Options

All in `backend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| OLLAMA_BASE_URL | http://localhost:11434 | Ollama API endpoint |
| OLLAMA_MODEL | mistral | Model to use |
| OLLAMA_TIMEOUT | 30 | Timeout in seconds |

## Available Models

- `mistral` (default) - Fast, balanced
- `llama2` - Good performance
- `codellama` - Code-focused
- `llama3` - Latest, powerful
- `phi` - Small, fast

Install any with: `ollama pull <model-name>`

## That's It!

You now have AI-powered conversational chat in ScareVerse! 🚀

For questions or issues, see the full documentation in `OLLAMA_CHAT_INTEGRATION.md`.
