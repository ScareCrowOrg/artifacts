---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - langchain
  - memory
  - summarization
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Conversation Memory - LangChain-Based Memory Management

This document details the conversation memory system using LangChain's `ConversationSummaryBufferMemory` with automatic summarization.

## Overview

The Conversation Memory system provides stateful, automatic conversation management using LangChain. It uses **Ollama/Mistral** by default for cost-efficient local summarization, eliminating external API costs.

## Features

- Session-based memory management (multi-user/session support)
- Automatic summarization of old messages when token limit is reached
- Token limit management with configurable thresholds
- Integration with LangChain `ConversationSummaryBufferMemory`
- **Cost-free summarization using Ollama/Mistral** (local LLM)
- In-memory session store with per-session isolation

## Architecture

### Memory Types

The project uses **LangChain-Based Memory** (`conversation_memory.py`) as the PRIMARY approach:

**Type:** Stateful, automatic  
**Used by:** Orchestrator (instruction_receiver.py, response_generator.py)  
**LLM:** Ollama/Mistral (local, cost-free) ✅

**Benefits:**
- Fully automatic memory management
- No manual threshold checks required
- LangChain's battle-tested implementation
- Zero API costs (uses Ollama/Mistral)

## Usage

### Basic Usage

```python
from backend.app.utils.conversation_memory import get_session_memory

# Get or create session memory (uses Ollama/Mistral by default)
memory = get_session_memory(session_id="user_123")

# Add user-assistant exchange
memory.add_exchange(
    user_message="What is the architecture?",
    ai_response="The architecture consists of a FastAPI backend with MongoDB..."
)

# Add another exchange
memory.add_exchange(
    user_message="How does authentication work?",
    ai_response="Authentication uses Google OAuth2 with JWT tokens..."
)

# Get conversation history as list of dicts
history = memory.get_history_as_dicts()
# Returns: [
#   {'role': 'user', 'content': 'What is the architecture?'},
#   {'role': 'assistant', 'content': 'The architecture consists of...'},
#   {'role': 'user', 'content': 'How does authentication work?'},
#   {'role': 'assistant', 'content': 'Authentication uses Google OAuth2...'},
# ]

# Get summary (if old messages were auto-summarized by Ollama/Mistral)
summary = memory.get_summary()
# Returns: "The user asked about architecture and authentication. 
#           I explained the FastAPI backend structure and OAuth2 flow."

# Clear history
memory.clear_history()
```

### Custom LLM Configuration

While Ollama/Mistral is the default (and recommended), you can customize:

```python
from backend.app.utils.conversation_memory import ConversationMemoryManager
from langchain_community.chat_models import ChatOllama

# Use a different Ollama model
custom_llm = ChatOllama(
    model="phi",  # Faster, lighter model
    base_url="http://localhost:11434"
)
memory = ConversationMemoryManager(llm=custom_llm)

# Or use OpenAI (requires API key - NOT RECOMMENDED due to costs)
from langchain_openai import ChatOpenAI
openai_llm = ChatOpenAI(model="gpt-3.5-turbo", api_key="sk-...")
memory = ConversationMemoryManager(llm=openai_llm)
```

### Configurable Token Limits

```python
# Create memory with custom token limit
memory = ConversationMemoryManager(
    llm=ChatOllama(model="mistral"),
    max_token_limit=2000  # Summarize when history exceeds 2000 tokens
)

# Default is 3000 tokens
```

## Session Management

### Global Session Store

The system maintains a global session store for multi-user/session support:

```python
from backend.app.utils.conversation_memory import get_session_store

# Get global session store (singleton)
store = get_session_store()

# Get or create session
memory = store.get_or_create_session("user_123")

# Get existing session (returns None if not found)
memory = store.get_session("user_123")

# Delete session
store.delete_session("user_123")

# Clear all sessions
store.clear_all_sessions()

# Get active session count
count = store.get_active_session_count()
print(f"Active sessions: {count}")
```

### Session Isolation

Each session maintains independent conversation history:

```python
# User A's session
memory_a = get_session_memory("user_a")
memory_a.add_exchange("Hello", "Hi there!")

# User B's session (completely independent)
memory_b = get_session_memory("user_b")
memory_b.add_exchange("What is this?", "This is ScareVerse backend")

# Histories are isolated
history_a = memory_a.get_history_as_dicts()  # Only user A's messages
history_b = memory_b.get_history_as_dicts()  # Only user B's messages
```

## How Automatic Summarization Works

### Summarization Trigger

When the conversation history exceeds the token limit (default: 3000 tokens), LangChain automatically:

1. Generates a summary of the oldest messages using Ollama/Mistral
2. Removes those old messages from history
3. Keeps the summary + recent messages in memory

This happens **transparently** without any manual intervention.

### Example Flow

```python
memory = get_session_memory("user_123")

# Turns 1-10: Messages accumulate in history
for i in range(10):
    memory.add_exchange(f"Question {i}", f"Answer {i}")

# After turn 10, if token limit exceeded:
# - LangChain calls Ollama/Mistral to summarize turns 1-7
# - Turns 1-7 are removed
# - Summary + turns 8-10 remain in memory

# Get current state
history = memory.get_history_as_dicts()  # Only recent turns
summary = memory.get_summary()  # Summary of older turns
```

### Cost Optimization

**All summarization uses Ollama/Mistral (local):**
- Zero API costs
- Fast summarization (~1-2 seconds per summary)
- No external dependencies
- Privacy-preserving (data never leaves your server)

## Integration with Orchestrator

The Conversation Memory is automatically integrated into the Chat Orchestrator:

```python
from backend.app.orchestrator import ChatOrchestrator

orchestrator = ChatOrchestrator()

# The orchestrator automatically:
# 1. Retrieves session memory
# 2. Includes conversation history in prompts
# 3. Updates memory after each response
# 4. Triggers summarization when needed (transparent)

result = orchestrator.process(
    mensagem="Continue our discussion about authentication",
    responsavel_id="user123",
    modelo="mistral",
    session_id="session_123"  # Links to conversation memory
)
```

### How Context is Injected

```python
# Internal orchestrator logic (simplified):
memory = get_session_memory(session_id)

# Build prompt with conversation history
history = memory.get_history_as_dicts()
summary = memory.get_summary()

prompt = f"""
{summary if summary else ''}

Conversation History:
{format_history(history)}

User: {current_message}
"""

# Call LLM with full context
response = llm.invoke(prompt)

# Update memory with response
memory.add_exchange(current_message, response)
```

## Testing

### Unit Tests

```python
def test_session_memory_creation():
    memory = get_session_memory("test_session")
    assert memory is not None
    assert isinstance(memory, ConversationMemoryManager)

def test_add_exchange():
    memory = get_session_memory("test_session")
    memory.clear_history()
    
    memory.add_exchange(
        user_message="Hello",
        ai_response="Hi there!"
    )
    
    history = memory.get_history_as_dicts()
    assert len(history) == 2
    assert history[0]['role'] == 'user'
    assert history[0]['content'] == 'Hello'
    assert history[1]['role'] == 'assistant'
    assert history[1]['content'] == 'Hi there!'

def test_automatic_summarization():
    # Create memory with low token limit
    memory = ConversationMemoryManager(
        llm=ChatOllama(model="mistral"),
        max_token_limit=100  # Very low for testing
    )
    
    # Add many exchanges to trigger summarization
    for i in range(20):
        memory.add_exchange(
            f"Question {i}: This is a long question...",
            f"Answer {i}: This is a detailed answer..."
        )
    
    # Should have summary due to token limit
    summary = memory.get_summary()
    assert summary is not None
    assert len(summary) > 0

def test_session_isolation():
    memory1 = get_session_memory("session_1")
    memory2 = get_session_memory("session_2")
    
    memory1.clear_history()
    memory2.clear_history()
    
    memory1.add_exchange("Question 1", "Answer 1")
    memory2.add_exchange("Question 2", "Answer 2")
    
    history1 = memory1.get_history_as_dicts()
    history2 = memory2.get_history_as_dicts()
    
    assert len(history1) == 2
    assert len(history2) == 2
    assert history1[0]['content'] == "Question 1"
    assert history2[0]['content'] == "Question 2"
```

### Integration Tests

```python
async def test_memory_with_orchestrator():
    orchestrator = ChatOrchestrator()
    session_id = "integration_test_session"
    
    # Clear previous state
    memory = get_session_memory(session_id)
    memory.clear_history()
    
    # First message
    result1 = await orchestrator.process(
        mensagem="Hello, I'm testing memory",
        responsavel_id="test_user",
        session_id=session_id
    )
    
    # Second message (should have context from first)
    result2 = await orchestrator.process(
        mensagem="Do you remember what I said?",
        responsavel_id="test_user",
        session_id=session_id
    )
    
    # Verify memory was used
    memory = get_session_memory(session_id)
    history = memory.get_history_as_dicts()
    assert len(history) >= 4  # At least 2 exchanges
```

## Performance Considerations

### Memory Usage

Each session stores conversation history in memory. For production systems with many users:

```python
# Monitor active sessions
store = get_session_store()
count = store.get_active_session_count()

# Implement session cleanup for inactive sessions
# (recommendation: clear sessions after 24 hours of inactivity)
```

### Summarization Performance

Summarization with Ollama/Mistral typically takes 1-2 seconds:

- **Mistral**: ~1.5 seconds per summary (recommended)
- **Phi**: ~0.8 seconds per summary (faster, less accurate)
- **DeepSeek**: ~2.5 seconds per summary (slower, more accurate)

This is triggered automatically and doesn't block the main conversation flow.

### Token Limit Tuning

Adjust token limits based on your use case:

```python
# Short-term memory (more frequent summarization)
memory = ConversationMemoryManager(max_token_limit=1500)

# Long-term memory (less frequent summarization)
memory = ConversationMemoryManager(max_token_limit=5000)

# Default (balanced)
memory = ConversationMemoryManager(max_token_limit=3000)
```

**Trade-offs:**
- Lower limit = More frequent summarization = Less context per call
- Higher limit = Less frequent summarization = More context per call

## Troubleshooting

### Ollama Not Running

```
Error: Could not connect to Ollama at http://localhost:11434
```

**Solution:**
1. Verify Ollama is installed: `ollama --version`
2. Start Ollama service: `ollama serve`
3. Check it's running: `curl http://localhost:11434/api/tags`

### Memory Not Persisting

If memory is lost between requests:

**Cause:** Session ID not being passed consistently

**Solution:**
```python
# Ensure session_id is consistent across requests
session_id = request.headers.get('X-Session-ID')
memory = get_session_memory(session_id)
```

### Summarization Not Working

If conversation history grows indefinitely without summarization:

**Cause:** Token limit too high or summarization failing

**Solution:**
1. Check Ollama is running and model is available
2. Lower the token limit:
   ```python
   memory = ConversationMemoryManager(max_token_limit=2000)
   ```
3. Verify model works:
   ```bash
   ollama run mistral "Summarize: The user asked about auth. I explained OAuth2."
   ```

### Session Conflicts

If users see each other's conversations:

**Cause:** Session IDs colliding or not being used

**Solution:**
```python
# Use unique session IDs per user
import uuid
session_id = f"user_{user_id}_{uuid.uuid4()}"
```

## Migration from Legacy System

If migrating from the legacy `chat_history_manager.py` system:

### Old Way (Manual)

```python
from backend.app.utils.chat_history_manager import (
    update_history, 
    should_summarize,
    build_summarization_prompt
)

# Manual management
state = update_history(state, user_msg, agent_response)
if should_summarize(state):
    prompt = build_summarization_prompt(state)
    # ... manual summarization logic
```

### New Way (Automatic)

```python
from backend.app.utils.conversation_memory import get_session_memory

# Automatic management
memory = get_session_memory(session_id)
memory.add_exchange(user_msg, agent_response)
# Summarization happens automatically!
```

### Migration Steps

1. Replace `chat_history_manager` imports with `conversation_memory`
2. Replace state dict with `ConversationMemoryManager` instance
3. Replace manual `update_history` calls with `memory.add_exchange()`
4. Remove manual `should_summarize()` and summarization logic
5. Use `memory.get_history_as_dicts()` to get conversation context

## Configuration

Environment variables in `.env`:

```bash
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral  # Default model for summarization

# Memory Configuration
MEMORY_MAX_TOKEN_LIMIT=3000  # Token limit before summarization
MEMORY_SESSION_TIMEOUT=86400  # Session timeout in seconds (24 hours)
```

## Related Documentation

- [Document Ingestion](./DOCUMENT_INGESTION.md) - Building the RAG vector store
- [Input Processor](./INPUT_PROCESSOR.md) - Priority-based context retrieval
- [Main README](./README.md) - Utils module overview
- [Orchestrator Documentation](../orchestrator/README.md) - Chat orchestration
- [LangChain Documentation](https://python.langchain.com/) - LangChain reference