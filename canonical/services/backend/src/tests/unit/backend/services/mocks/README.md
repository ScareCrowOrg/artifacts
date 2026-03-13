---
processed: true
processed_date: 2025-12-10
themes:
  - testing
  - mocks
  - unit-tests
modules:
  - backend
code_verified: true
dead_docs_found: true
corrections_made: "Updated example to use actual mock class (MockHttpxAsyncClient) instead of non-existent MockOpenAIClient"
---

# Backend Unit Tests - Service Mocks

## Overview

Mock implementations for service layer dependencies used in backend unit tests.

## Available Mocks

This directory provides mocks for:
- **HTTP/HTTPX clients** - `MockHttpxAsyncClient`, `MockHttpxResponse`
- **OpenAI API responses** - Factory functions for assistant, thread, message, run, file responses
- External API integrations
- Network requests

## Exported Mocks

From `tests.unit.backend.services.mocks`:
- `MockHttpxAsyncClient` - Mock async HTTP client
- `MockHttpxResponse` - Mock HTTP response
- `create_mock_assistant_response()` - OpenAI Assistant API response
- `create_mock_thread_response()` - OpenAI Thread API response
- `create_mock_message_response()` - OpenAI Message API response
- `create_mock_run_response()` - OpenAI Run API response
- `create_mock_file_response()` - OpenAI File API response
- `create_mock_file_list_response()` - OpenAI File List API response
- `create_mock_delete_response()` - OpenAI Delete API response

**Code Reference**: `backend/tests/unit/backend/services/mocks/__init__.py`

## Usage Example

```python
from tests.unit.backend.services.mocks import (
    MockHttpxAsyncClient,
    create_mock_assistant_response
)

def test_service_with_mocked_httpx():
    # Create mock client
    mock_client = MockHttpxAsyncClient()
    
    # Setup mock response
    mock_assistant = create_mock_assistant_response(
        assistant_id='asst_123',
        name='Test Assistant'
    )
    mock_client.add_response(200, mock_assistant)
    
    # Use in service test
    service = AssistantService(http_client=mock_client)
    result = await service.create_assistant(name='Test')
    
    assert result['id'] == 'asst_123'
```

## Files

- `openai_mock.py` - OpenAI API mocks and response factories
- `__init__.py` - Exports all available mocks

---

For more details, see [Backend Tests README](../../../README.md)
