---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - ai
  - gemini
  - api
modules:
  - backend
  - ai-integration
code_verified: true
dead_docs_found: false
---
# Gemini Files API Integration

## Overview

This document describes the implementation of Gemini Files API integration for handling attachments in chat conversations. The implementation optimizes token usage by uploading files separately instead of injecting raw content into prompts.

## Key Changes

### 1. Output Token Limit Increase
- **Changed**: `maxOutputTokens` from 1024 to 4096
- **Location**: `backend/app/gemini_service.py` line 220
- **Impact**: Allows for longer, more complete responses from Gemini

### 2. Response Concatenation Fix
- **Changed**: Response text extraction now concatenates all parts
- **Location**: `backend/app/gemini_service.py` line 251
- **Before**: `response_text = parts[0].get("text", "")`
- **After**: `response_text = "".join([part.get("text", "") for part in parts])`
- **Impact**: Prevents response truncation when Gemini returns multiple parts

### 3. Files API Integration

#### New Function: `upload_arquivo_gemini`
**Location**: `backend/app/gemini_service.py` lines 18-102

Uploads files to Gemini Files API using multipart/form-data.

**Parameters**:
- `file_content` (str): Content of the file as string
- `file_name` (str): Name of the file
- `mime_type` (str): MIME type (default: "text/plain")
- `api_key` (Optional[str]): API key (uses global config if not provided)

**Returns**: File URI from Gemini (e.g., `https://generativelanguage.googleapis.com/v1beta/files/abc123`)

**Example**:
```python
file_uri = await upload_arquivo_gemini(
    file_content="def hello(): print('Hello')",
    file_name="script.py",
    mime_type="text/x-python",
    api_key="your_api_key"
)
```

#### Modified Function: `montar_prompt_conversacional_gemini`
**Location**: `backend/app/gemini_service.py` lines 107-204

Now accepts optional `file_uris` parameter to include file attachments.

**New Parameter**:
- `file_uris` (Optional[List[str]]): List of file URIs from Files API

**Example**:
```python
prompt = montar_prompt_conversacional_gemini(
    historico=conversation_history,
    nova_intencao="Analyze these files",
    file_uris=[
        "https://generativelanguage.googleapis.com/v1beta/files/abc123",
        "https://generativelanguage.googleapis.com/v1beta/files/def456"
    ]
)
```

#### Modified Function: `processar_chat_com_gemini`
**Location**: `backend/app/gemini_service.py` lines 274-310

Now accepts and passes `file_uris` to prompt assembly.

**New Parameter**:
- `file_uris` (Optional[List[str]]): List of file URIs from Files API

### 4. Chat Router Updates
**Location**: `backend/app/chat_router.py` lines 133-159

The chat router now:
1. Detects when provider is Gemini
2. Uploads each attachment via Files API
3. Collects file URIs
4. Passes URIs to `processar_chat_com_gemini`
5. Falls back to legacy mode (raw content injection) for non-Gemini providers

**Flow**:
```python
if modelo_provider == "gemini":
    # Use Files API
    for anexo in request.anexos:
        file_uri = await upload_arquivo_gemini(
            file_content=anexo.conteudo,
            file_name=anexo.nome,
            mime_type="text/plain",
            api_key=modelo_api_key
        )
        file_uris.append(file_uri)
else:
    # Legacy mode: inject content into prompt
    intencao_completa += f"\n[Anexo: {anexo.nome}]\n{anexo.conteudo}\n"
```

## Benefits

1. **Reduced Token Consumption**: Files are uploaded separately, not counted in prompt tokens
2. **Better Performance**: Faster processing with optimized token usage
3. **Complete Responses**: Increased output token limit and proper concatenation
4. **Provider Flexibility**: Legacy mode maintained for non-Gemini providers

## Testing

### Unit Tests
**Location**: `backend/tests/unit/test_gemini_service.py`

Coverage: 15 tests
- Upload functionality (success, failure, errors)
- Prompt generation with/without files
- API call validation
- Token limit verification

### Integration Tests
**Location**: `backend/tests/integration/test_gemini_files_api.py`

Coverage: 5 tests
- End-to-end file upload and chat flow
- Multiple file handling
- Error handling
- Network error scenarios

**Run tests**:
```bash
cd backend
python -m pytest tests/unit/test_gemini_service.py -v
python -m pytest tests/integration/test_gemini_files_api.py -v
```

## API Reference

### Gemini Files API Endpoint
```
POST https://generativelanguage.googleapis.com/upload/v1beta/files
```

**Headers**:
- `X-Goog-Api-Key`: Your Gemini API key

**Body**: multipart/form-data with file

**Response**:
```json
{
  "file": {
    "uri": "https://generativelanguage.googleapis.com/v1beta/files/{file_id}",
    "name": "files/{file_id}",
    "mimeType": "text/plain"
  }
}
```

### Using Files in Prompts

Files are referenced in the `parts` array of a user message:

```python
{
  "role": "user",
  "parts": [
    {"text": "Analyze this file"},
    {"fileData": {"fileUri": "https://generativelanguage.googleapis.com/v1beta/files/abc123"}}
  ]
}
```

## Configuration

No additional configuration required. Uses existing:
- `GEMINI_API_KEY`: From `.env` or model-specific API key
- `GEMINI_API_URL`: Base URL for Gemini API
- `GEMINI_TIMEOUT`: Request timeout

## Error Handling

The implementation includes comprehensive error handling:

1. **Upload Failures**: Logged as warnings, chat continues without files
2. **Invalid Responses**: ValueError with descriptive message
3. **Network Errors**: HTTPError or TimeoutException propagated
4. **Missing API Key**: ValueError with configuration instructions

## Migration Notes

### Backward Compatibility
- Non-Gemini providers (Ollama) continue using raw content injection
- No breaking changes to existing API contracts
- Graceful degradation if file upload fails

### Future Improvements
1. Support for binary files (images, PDFs)
2. File caching to avoid re-uploading same files
3. File size limits and validation
4. Progress tracking for large file uploads

## Related Documentation
- [Chat IA Integration](./CHAT_IA_INTEGRATION.md)
- [Model Selection Guide](./MODEL_SELECTION_GUIDE.md)
- [LangChain/LangGraph Implementation](./LANGCHAIN_LANGGRAPH_IMPLEMENTATION.md)
