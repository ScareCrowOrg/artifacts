---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - ai
  - openai
  - assistant
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# OpenAI Assistant Module

This module provides integration with OpenAI's Assistants API for holistic conversation management with file contextualization.

## Overview

The OpenAI Assistant module is a modularized service that wraps the OpenAI Assistants API v2, providing a clean interface for creating assistants, managing conversation threads, handling messages, and orchestrating complete conversation flows.

## Module Structure

```
openai_assistant/
├── __init__.py              # Public API exports
├── assistant_manager.py     # Assistant creation and retrieval
├── thread_manager.py        # Thread operations (create, get)
├── message_manager.py       # Message operations (add, retrieve)
├── run_manager.py          # Run execution and polling
├── orchestrator.py         # High-level process_with_assistant
└── README.md               # This file
```

## Components

### 1. Assistant Manager (`assistant_manager.py`)

Handles assistant creation and retrieval.

**Functions:**
- `create_or_get_assistant(name, instructions, model, tools, api_key)`: Create or retrieve an assistant

**Example:**
```python
from app.services.openai_assistant import create_or_get_assistant

assistant_id = await create_or_get_assistant(
    name="ScareVerse Lab Agent",
    instructions="You are a helpful coding assistant.",
    model="gpt-4o-mini"
)
```

### 2. Thread Manager (`thread_manager.py`)

Manages conversation threads.

**Functions:**
- `create_thread(api_key)`: Create a new conversation thread
- `get_thread(thread_id, api_key)`: Retrieve an existing thread

**Example:**
```python
from app.services.openai_assistant import create_thread, get_thread

# Create new thread
thread_id = await create_thread()

# Retrieve existing thread
thread = await get_thread(thread_id)
```

### 3. Message Manager (`message_manager.py`)

Handles message operations.

**Functions:**
- `add_message_to_thread(thread_id, content, role, file_ids, api_key)`: Add message with optional file attachments
- `get_run_messages(thread_id, api_key, limit)`: Retrieve messages from a thread

**Example:**
```python
from app.services.openai_assistant import add_message_to_thread, get_run_messages

# Add message with files
message_id = await add_message_to_thread(
    thread_id="thread_abc123",
    content="Explain this code",
    file_ids=["file-abc123"]
)

# Get messages
messages = await get_run_messages("thread_abc123")
```

### 4. Run Manager (`run_manager.py`)

Executes assistant runs and polls for completion.

**Functions:**
- `run_assistant(thread_id, assistant_id, api_key, poll_interval, max_poll_time)`: Run assistant and wait for completion

**Constants:**
- `DEFAULT_POLL_INTERVAL`: 1.0 second
- `DEFAULT_MAX_POLL_TIME`: 120.0 seconds (2 minutes)

**Example:**
```python
from app.services.openai_assistant import run_assistant

run = await run_assistant(
    thread_id="thread_abc123",
    assistant_id="asst_abc123"
)
```

### 5. Orchestrator (`orchestrator.py`)

High-level orchestration for complete conversation flow.

**Functions:**
- `process_with_assistant(user_message, thread_id, assistant_id, file_paths, system_instructions, model, api_key)`: Complete conversation flow

**Example:**
```python
from pathlib import Path
from app.services.openai_assistant import process_with_assistant

response, thread_id, assistant_id = await process_with_assistant(
    user_message="Explain this code",
    file_paths=[Path("main.py")],
    system_instructions="You are a helpful code assistant.",
    api_key="sk-..."
)
```

## Usage Patterns

### Simple Conversation (No Files)

```python
from app.services.openai_assistant import process_with_assistant

response, thread_id, assistant_id = await process_with_assistant(
    user_message="What is the purpose of this project?",
    system_instructions="You are a helpful assistant."
)
print(response)
```

### Conversation with File Context

```python
from pathlib import Path
from app.services.openai_assistant import process_with_assistant

response, thread_id, assistant_id = await process_with_assistant(
    user_message="Analyze this file and suggest improvements",
    file_paths=[Path("backend/app/main.py")],
    system_instructions="You are a code review assistant."
)
print(response)
```

### Multi-turn Conversation

```python
from app.services.openai_assistant import process_with_assistant

# First turn
response1, thread_id, assistant_id = await process_with_assistant(
    user_message="What does this function do?",
    file_paths=[Path("utils.py")]
)

# Second turn (reuse thread and assistant)
response2, _, _ = await process_with_assistant(
    user_message="Can you suggest optimizations?",
    thread_id=thread_id,
    assistant_id=assistant_id
)
```

### Manual Control (Low-level API)

```python
from pathlib import Path
from app.services.openai_assistant import (
    create_or_get_assistant,
    create_thread,
    add_message_to_thread,
    run_assistant,
    get_run_messages
)
from app.services.openai_files_api import upload_file_to_openai_api

# Upload file
file_id = await upload_file_to_openai_api(
    file_path=Path("code.py"),
    purpose="assistants"
)

# Create assistant with file_search tool
assistant_id = await create_or_get_assistant(
    name="Code Analyzer",
    instructions="Analyze code and provide feedback",
    tools=[{"type": "file_search"}]
)

# Create thread
thread_id = await create_thread()

# Add message
message_id = await add_message_to_thread(
    thread_id=thread_id,
    content="Review this code",
    file_ids=[file_id]
)

# Run assistant
run = await run_assistant(
    thread_id=thread_id,
    assistant_id=assistant_id
)

# Get response
messages = await get_run_messages(thread_id)
response = messages[0]['content'][0]['text']['value']
```

## Configuration

The module uses configuration from `app.config`:

- `OPENAI_API_KEY`: OpenAI API key (required)
- `OPENAI_API_URL`: Base URL for OpenAI API (default: https://api.openai.com/v1)
- `OPENAI_TIMEOUT`: HTTP timeout in seconds
- `OPENAI_DEFAULT_MODEL`: Default model to use (e.g., "gpt-4o-mini")

## Error Handling

All functions raise appropriate exceptions:

- `ValueError`: For missing API key or invalid parameters
- `httpx.HTTPError`: For HTTP communication errors with OpenAI
- `httpx.TimeoutException`: For timeout errors
- `TimeoutError`: When run polling exceeds max_poll_time
- `RuntimeError`: For processing errors in orchestrator

## Backward Compatibility

This modularized structure maintains full backward compatibility with the original `openai_assistant_service.py`. All imports that previously used:

```python
from app.services.openai_assistant_service import process_with_assistant
```

Can now use:

```python
from app.services.openai_assistant import process_with_assistant
```

The original file has been converted to a shim that re-exports from this module.

## Technical Details

- **API Version**: OpenAI Assistants API v2
- **Async/Await**: All functions are async and use `httpx.AsyncClient`
- **File Attachments**: Uses `file_search` tool for file contextualization
- **Run Polling**: Configurable polling interval and max poll time
- **Logging**: Comprehensive logging using Python's `logging` module

## Testing

See `tests/unit/backend/test_openai_assistant_service.py` and `tests/integration/backend/test_openai_assistants_integration.py` for test examples.

## Related Modules

- `openai_files_api.py`: File upload operations
- `providers/openai_provider.py`: OpenAI provider integration
- `openai_service.py`: Legacy OpenAI service

## References

- [OpenAI Assistants API Documentation](https://platform.openai.com/docs/assistants/overview)
- [ScareVerse RULESET.md](../../../../RULESET.md)
- [Backend Architecture](../../../../docs/ARQUITETURA_TESTES.md)
