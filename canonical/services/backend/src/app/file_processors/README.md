---
processed: true
processed_date: 2025-12-08
themes:
  - architecture
  - backend
  - modules
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# File Processors Module

This module provides utilities for optimizing file content before sending to OpenAI API. It handles token counting, file segmentation, documentation minimization, and context preservation.

## Index

### Files
- `__init__.py` - Module exports
- `token_counter.py` - Token counting utilities using tiktoken
- `content_minimizer.py` - Comment and docstring removal
- `file_segmenter.py` - File segmentation by token limits
- `message_builder.py` - OpenAI message construction from segments

### Key Concepts
- Token counting and limit management
- Content minimization (remove comments/docstrings)
- Intelligent file segmentation
- Message building for API calls

## Overview

When sending source code files (.py, .yml) to OpenAI API, token limits can be exceeded. This module solves that by:

1. **Token Counting**: Accurate token counting using tiktoken library
2. **Content Minimization**: Remove comments/docstrings to reduce token usage
3. **File Segmentation**: Split large files into logical chunks (by functions for .py, by sections for .yml)
4. **Context Maintenance**: Preserve conversation context across segments
5. **Error Handling**: Robust error management for API transmission

## Modules

### `token_counter.py`
Provides token counting utilities using OpenAI's tiktoken library.

**Functions:**
- `count_tokens(text, model)`: Count tokens in text
- `estimate_message_tokens(messages, model)`: Estimate tokens for message list
- `check_token_limit(text, max_tokens, model)`: Check if text is within limit
- `get_available_tokens(messages, max_context, model)`: Calculate available tokens

### `content_minimizer.py`
Removes comments and docstrings from source code to minimize token usage.

**Functions:**
- `remove_python_comments_and_docstrings(code)`: Remove Python docs
- `remove_yaml_comments(yaml_content)`: Remove YAML comments
- `should_minimize_file(file_name)`: Determine if file should be minimized

### `file_segmenter.py`
Segments large files into smaller chunks based on token limits.

**Functions:**
- `segment_python_file(code, max_tokens, model)`: Segment by functions/classes
- `segment_yaml_file(yaml_content, max_tokens, model)`: Segment by top-level keys
- `process_file_for_openai(file_content, file_name, ...)`: Main entry point

### `message_builder.py`
Builds OpenAI message lists with segmented content.

**Functions:**
- `build_segmented_messages(base_messages, file_segments, user_message, ...)`: Build message groups
- `format_file_reference(file_name, segment_index, ...)`: Format file headers
- `merge_segment_responses(responses)`: Merge responses from multiple segments

## Usage Examples

### Basic File Processing

```python
from app.file_processors import process_file_for_openai

# Read a Python file
with open("example.py", "r") as f:
    code = f.read()

# Process for OpenAI (minimize docs, segment if needed)
segments = process_file_for_openai(
    file_content=code,
    file_name="example.py",
    max_tokens=8000,
    minimize_docs=True,
    model="gpt-3.5-turbo"
)

# segments is a list of dicts with 'content', 'metadata', 'tokens'
for segment in segments:
    print(f"Segment: {segment['metadata']['segment_name']}")
    print(f"Tokens: {segment['tokens']}")
```

### Building Messages with Segments

```python
from app.file_processors import build_segmented_messages

# Conversation history
history = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"}
]

# Build message groups (handles token limits)
message_groups = build_segmented_messages(
    base_messages=history,
    file_segments=segments,
    user_message="Analyze this code for bugs",
    max_context_tokens=16000
)

# Send each group to OpenAI
for messages in message_groups:
    response = await chamar_openai({"model": "gpt-3.5-turbo", "messages": messages})
    # Process response...
```

### Integration with OpenAI Service

```python
from app.file_processors import process_file_for_openai, build_segmented_messages
from app.openai_service import chamar_openai

async def process_file_with_openai(file_path: str, user_question: str):
    # Read file
    with open(file_path, "r") as f:
        content = f.read()
    
    # Process file
    segments = process_file_for_openai(
        file_content=content,
        file_name=file_path,
        max_tokens=8000
    )
    
    # Build messages
    message_groups = build_segmented_messages(
        base_messages=[],
        file_segments=segments,
        user_message=user_question
    )
    
    # Call OpenAI for each group
    responses = []
    for messages in message_groups:
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "temperature": 0.7
        }
        result = await chamar_openai(payload)
        responses.append(result["choices"][0]["message"]["content"])
    
    # Merge responses if multiple segments
    if len(responses) > 1:
        from app.file_processors import merge_segment_responses
        return merge_segment_responses(responses)
    else:
        return responses[0]
```

## Configuration

### Token Limits

Token limits are defined in `token_counter.py`:

```python
DEFAULT_MAX_TOKENS = 8000  # Conservative limit per segment
DEFAULT_MODEL_CONTEXT = 16000  # Default context window
RESPONSE_BUFFER_TOKENS = 2000  # Reserve for response
```

Adjust these based on your OpenAI model:
- GPT-3.5 Turbo: 16k tokens context
- GPT-4: 8k tokens context (standard), 32k tokens (extended)
- GPT-4 Turbo: 128k tokens context

### File Types Supported

- **Python (.py)**: Segmented by functions, classes, and top-level statements
- **YAML (.yml, .yaml)**: Segmented by top-level keys
- **Other files**: Simple line-based segmentation

## Dependencies

- `tiktoken`: OpenAI's token counting library (required)
- `PyYAML`: For YAML parsing (optional, falls back to simple parsing)
- `astor`: For Python AST to source conversion (optional)

Add to `requirements.txt`:
```
tiktoken>=0.5.0
PyYAML>=6.0
```

## Error Handling

The module includes robust error handling:

- **Empty files**: Raises `ValueError`
- **Syntax errors in Python**: Falls back to unparseable segment
- **YAML parse errors**: Falls back to simple segmentation
- **Token limit exceeded**: Warns but continues processing
- **tiktoken unavailable**: Falls back to approximate counting (chars/4)

## Testing

See `tests/unit/test_file_processors/` for comprehensive test coverage.

Run tests:
```bash
pytest tests/unit/test_file_processors/ -v
```

## Security Considerations

- **Path Validation**: File paths should be validated before reading
- **Size Limits**: Large files (>10MB) should be rejected before processing
- **Content Sanitization**: No sensitive data should be logged
- **Token Counting**: Always verify token counts before API calls

## Performance

- **Token Counting**: Fast (<1ms per file)
- **Segmentation**: Linear time O(n) based on file size
- **Memory**: Keeps entire file content in memory (consider streaming for very large files)

## Testing

### Running Tests

All file_processors modules have comprehensive test coverage (≥90% goal as per RULESET.md Rule 3.1).

**Run all file_processors tests:**
```bash
cd backend
pytest tests/unit/backend/file_processors/ -v --cov=app/file_processors --cov-report=term-missing
```

**Run specific module tests:**
```bash
# Token counter tests
pytest tests/unit/backend/file_processors/test_token_counter.py -v

# Content minimizer tests
pytest tests/unit/backend/file_processors/test_content_minimizer.py -v

# File segmenter tests
pytest tests/unit/backend/file_processors/test_file_segmenter.py -v

# Message builder tests
pytest tests/unit/backend/file_processors/test_message_builder.py -v
```

### Test Coverage Summary

| Module | Coverage | Tests | Status |
|--------|----------|-------|--------|
| token_counter.py | **100%** | 23 | ✅ Perfect |
| content_minimizer.py | 100% | 27 | ✅ Excellent |
| file_segmenter.py | **97%** | 24 | ✅ Excellent |
| message_builder.py | 100% | 18 | ✅ Excellent |

**Overall:** **99%** average coverage across all modules (exceeds 90% target)

### Test Files

- `tests/unit/backend/file_processors/test_token_counter.py` - Token counting functions (23 tests, 100% coverage)
- `tests/unit/backend/file_processors/test_content_minimizer.py` - Comment/docstring removal (27 tests, 100% coverage)
- `tests/unit/backend/file_processors/test_file_segmenter.py` - File segmentation (24 tests, 97% coverage)
- `tests/unit/backend/file_processors/test_message_builder.py` - Message building (18 tests, 100% coverage)

**Total: 92 tests with 99% average coverage**

### Test Dependencies

```bash
pip install pytest pytest-cov tiktoken PyYAML
```

## Integration with Existing Code

This module integrates with:
- `openai_service.py`: Use processed segments with `chamar_openai()`
- `chat_router.py`: Process attachments before sending to API
- `document_tools.py`: Enhance file reading with segmentation

## Compliance

- **Rule 1.1**: Each module <500 lines ✅
- **Rule 2.1**: README.md provided ✅
- **Rule 3.1**: Tests provided with **99%** coverage (exceeds 90% target) ✅
- **Rule 4.1**: No hardcoded configuration ✅
- **Rule 4.3**: Technical names in English ✅

## Future Enhancements

- Streaming support for very large files
- More language support (JavaScript, Java, etc.)
- Intelligent comment preservation (keep important comments)
- Semantic segmentation using language models
- Caching of token counts for repeated files

## References

- [OpenAI Token Limits](https://platform.openai.com/docs/models)
- [tiktoken Documentation](https://github.com/openai/tiktoken)
- [Project RULESET.md](../../../RULESET.md)
- [Backend README](../../README.md)
