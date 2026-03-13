---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - api
  - tracing
  - chat
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Conversation Trace API - Usage Guide

## Overview

The Conversation Trace API provides endpoints for retrieving and analyzing conversation trace data captured during RAG pipeline execution. This guide covers how to use the trace retrieval and export functionality.

## Table of Contents

- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
  - [Get Trace by Conversation ID](#get-trace-by-conversation-id)
  - [List Recent Traces](#list-recent-traces)
- [Export Utilities](#export-utilities)
- [Usage Examples](#usage-examples)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)

---

## Authentication

All trace API endpoints require authentication via JWT token. Include the token in the `Authorization` header:

```
Authorization: Bearer <your_jwt_token>
```

Users can only access their own traces. Admin access control will be added in a future release.

---

## API Endpoints

### Get Trace by Conversation ID

Retrieve complete trace data for a specific conversation, including all captured fragments.

**Endpoint**: `GET /api/v1/traces/conversation/{conversation_id}`

**Parameters**:
- `conversation_id` (path): Unique identifier for the conversation

**Response**:
```json
{
  "trace_id": "cell_abc123",
  "conversation_id": "conv_xyz789",
  "session_id": "sess_456",
  "user_message": "How do I create a cell?",
  "target_llm": "openai",
  "created_at": "2025-11-18T10:00:00.000000",
  "fragments_count": 8,
  "fragments": [
    {
      "timestamp": "2025-11-18T10:00:01.000000",
      "conversation_id": "conv_xyz789",
      "stage": "initial_prompt",
      "data": {
        "user_message": "How do I create a cell?",
        "session_id": "sess_456",
        "target_llm": "openai"
      }
    },
    {
      "timestamp": "2025-11-18T10:00:02.500000",
      "conversation_id": "conv_xyz789",
      "stage": "rag_retrieval",
      "data": {
        "query": "create cell",
        "chunks_retrieved": 5,
        "collections_used": ["scareverse_docs"]
      }
    },
    ...
  ]
}
```

**Status Codes**:
- `200 OK`: Trace retrieved successfully
- `404 Not Found`: No trace found for the conversation ID
- `403 Forbidden`: User not authorized to view this trace
- `500 Internal Server Error`: Server error during retrieval

**Example**:
```bash
curl -X GET "http://localhost:8000/api/v1/traces/conversation/conv_abc123" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### List Recent Traces

Retrieve a paginated list of recent traces for the authenticated user.

**Endpoint**: `GET /api/v1/traces/recent`

**Query Parameters**:
- `limit` (optional): Maximum number of traces to return (1-100, default: 10)
- `offset` (optional): Number of traces to skip for pagination (default: 0)

**Response**:
```json
{
  "count": 25,
  "limit": 10,
  "offset": 0,
  "traces": [
    {
      "trace_id": "cell_abc123",
      "conversation_id": "conv_xyz789",
      "session_id": "sess_456",
      "user_message": "How do I create a cell?",
      "target_llm": "openai",
      "created_at": "2025-11-18T10:00:00.000000",
      "fragments_count": 8
    },
    {
      "trace_id": "cell_def456",
      "conversation_id": "conv_pqr321",
      "session_id": "sess_789",
      "user_message": "Explain RAG pipeline...",
      "target_llm": "gemini",
      "created_at": "2025-11-18T09:30:00.000000",
      "fragments_count": 7
    },
    ...
  ]
}
```

**Status Codes**:
- `200 OK`: Traces retrieved successfully
- `422 Unprocessable Entity`: Invalid query parameters
- `500 Internal Server Error`: Server error during retrieval

**Example - Default pagination**:
```bash
curl -X GET "http://localhost:8000/api/v1/traces/recent" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Example - Custom pagination**:
```bash
curl -X GET "http://localhost:8000/api/v1/traces/recent?limit=20&offset=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Export Utilities

The `trace_export.py` module provides utility functions for exporting and analyzing traces.

### Export to JSON

Export a trace cell to JSON format:

```python
from app.utils.trace_export import export_trace_to_json

# Export with pretty printing (default)
json_str = export_trace_to_json(trace_cell, pretty=True)
print(json_str)

# Export compact (no formatting)
json_str = export_trace_to_json(trace_cell, pretty=False)

# Export without metadata
json_str = export_trace_to_json(trace_cell, include_metadata=False)
```

### Summarize Trace Stages

Generate a summary of captured stages:

```python
from app.utils.trace_export import summarize_trace_stages

summary = summarize_trace_stages(trace_cell)

print(f"Total fragments: {summary['total_fragments']}")
print(f"Stages captured: {', '.join(summary['stages_captured'])}")
print(f"Duration: {summary['duration_ms']}ms")

# Access per-stage details
for stage, details in summary['stage_details'].items():
    print(f"{stage}: {details['count']} occurrences")
```

### Extract Stage Data

Extract fragments for a specific stage:

```python
from app.utils.trace_export import extract_stage_data

# Get all RAG retrieval fragments
rag_fragments = extract_stage_data(trace_cell, "rag_retrieval")

for fragment in rag_fragments:
    data = fragment['data']
    print(f"Retrieved {data.get('chunks_retrieved', 0)} chunks")
    print(f"Query: {data.get('query', 'N/A')}")
```

### Compare Traces

Compare two traces to identify differences:

```python
from app.utils.trace_export import compare_traces

comparison = compare_traces(trace_cell_1, trace_cell_2)

print(f"Common stages: {comparison['common_stages']}")
print(f"Unique to trace 1: {comparison['unique_to_trace_1']}")
print(f"Unique to trace 2: {comparison['unique_to_trace_2']}")
print(f"Fragment count diff: {comparison['fragment_count_diff']}")
```

---

## Usage Examples

### Example 1: Retrieve and Analyze a Trace

```python
import httpx
from app.utils.trace_export import summarize_trace_stages

# Retrieve trace via API
async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://localhost:8000/api/v1/traces/conversation/conv_abc123",
        headers={"Authorization": f"Bearer {token}"}
    )
    trace_data = response.json()

# Analyze stages
print(f"Captured {trace_data['fragments_count']} fragments")

for fragment in trace_data['fragments']:
    print(f"[{fragment['stage']}] at {fragment['timestamp']}")
```

### Example 2: List and Filter Recent Traces

```python
import httpx

async with httpx.AsyncClient() as client:
    # Get first page
    response = await client.get(
        "http://localhost:8000/api/v1/traces/recent?limit=20",
        headers={"Authorization": f"Bearer {token}"}
    )
    data = response.json()
    
    print(f"Total traces: {data['count']}")
    
    # Filter by LLM
    openai_traces = [
        t for t in data['traces'] 
        if t['target_llm'] == 'openai'
    ]
    print(f"OpenAI traces: {len(openai_traces)}")
```

### Example 3: Export Trace to File

```python
from app.database import db
from app.models.content import Celula
from app.utils.trace_export import export_trace_to_json

# Retrieve trace cell from database
trace_cells = db.find_many("celulas", Celula, is_canonical=False)
trace_cell = next(
    (c for c in trace_cells 
     if c.initial_data.get("conversation_id") == "conv_abc123"),
    None
)

if trace_cell:
    # Export to JSON file
    json_str = export_trace_to_json(trace_cell, pretty=True)
    
    with open(f"trace_{trace_cell.id}.json", "w") as f:
        f.write(json_str)
    
    print(f"Exported trace to trace_{trace_cell.id}.json")
```

### Example 4: Debug RAG Retrieval Issues

```python
from app.utils.trace_export import extract_stage_data

# Get trace and extract RAG retrieval fragments
trace_data = # ... retrieve via API
trace_cell = # ... get Celula instance

rag_fragments = extract_stage_data(trace_cell, "rag_retrieval")

for fragment in rag_fragments:
    data = fragment['data']
    chunks = data.get('chunks_retrieved', 0)
    query = data.get('query', 'N/A')
    
    if chunks < 3:
        print(f"WARNING: Low chunk count ({chunks}) for query: {query}")
        print(f"Collections used: {data.get('collections_used', [])}")
```

---

## Error Handling

### Common Errors

**404 Not Found**
```json
{
  "detail": "No trace found for conversation: conv_nonexistent"
}
```

Solution: Verify the conversation ID is correct and tracing was enabled for that conversation.

**403 Forbidden**
```json
{
  "detail": "Not authorized to view this trace"
}
```

Solution: Ensure you're authenticated as the user who owns the trace.

**422 Unprocessable Entity**
```json
{
  "detail": [
    {
      "loc": ["query", "limit"],
      "msg": "ensure this value is less than or equal to 100",
      "type": "value_error.number.not_le"
    }
  ]
}
```

Solution: Check that query parameters are within valid ranges (limit: 1-100, offset: >= 0).

**500 Internal Server Error**
```json
{
  "detail": "Error retrieving trace data"
}
```

Solution: Check server logs for detailed error information. This usually indicates a database or internal error.

---

## Best Practices

### 1. Enable Tracing Selectively

Tracing adds storage overhead. Enable it only when needed:

```python
# Enable tracing for specific conversations
request = ProcessarIntencaoChatRequest(
    intencao="How do I create a cell?",
    enable_tracing=True,  # Only when debugging
    ...
)
```

### 2. Use Pagination for Large Result Sets

Always use pagination when listing traces:

```python
# Good: Paginated requests
limit = 20
offset = 0

while True:
    response = await client.get(
        f"/api/v1/traces/recent?limit={limit}&offset={offset}",
        headers={"Authorization": f"Bearer {token}"}
    )
    data = response.json()
    
    # Process traces
    process_traces(data['traces'])
    
    # Check if more pages available
    if offset + limit >= data['count']:
        break
    
    offset += limit
```

### 3. Export Traces for Offline Analysis

Export traces to JSON for analysis in external tools:

```python
# Export trace
json_str = export_trace_to_json(trace_cell, pretty=True)

# Save to file
with open(f"traces/trace_{conversation_id}.json", "w") as f:
    f.write(json_str)
```

### 4. Monitor Trace Storage

Regularly check trace storage usage:

```python
# Count traces per user
trace_cells = db.find_many("celulas", Celula, is_canonical=False)
user_traces = [c for c in trace_cells if c.assignee_id == user_id]

print(f"Total traces: {len(user_traces)}")
print(f"Total fragments: {sum(len(c.fragments) for c in user_traces)}")
```

### 5. Clean Up Old Traces

Implement a cleanup policy for old traces:

```python
from datetime import datetime, timedelta

# Find traces older than 30 days
cutoff_date = datetime.utcnow() - timedelta(days=30)

old_traces = [
    c for c in trace_cells
    if c.dataCriacao < cutoff_date
]

# Archive or delete old traces
for trace in old_traces:
    # Export before deleting (optional)
    export_trace_to_json(trace)
    # Delete trace cell
    db.delete("celulas", trace.id, is_canonical=False)
```

---

## Configuration

Tracing can be configured via environment variables:

```bash
# Enable/disable tracing globally
ENABLE_CONVERSATION_TRACING=true

# Trace retention period (days)
TRACE_RETENTION_DAYS=30

# Max fragment size (bytes)
TRACE_MAX_FRAGMENT_SIZE=10000
```

Add these to your `.env` file or set them in your deployment environment.

---

## API Reference Summary

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/v1/traces/conversation/{id}` | GET | Get trace by conversation ID | Yes |
| `/api/v1/traces/recent` | GET | List recent traces | Yes |

## Utility Functions Summary

| Function | Description | Returns |
|----------|-------------|---------|
| `export_trace_to_json()` | Export trace to JSON string | `str` |
| `summarize_trace_stages()` | Generate stage summary | `Dict[str, Any]` |
| `extract_stage_data()` | Extract fragments for stage | `List[Dict[str, Any]]` |
| `compare_traces()` | Compare two traces | `Dict[str, Any]` |

---

## Support

For issues or questions about the Conversation Trace API:

1. Check server logs for detailed error messages
2. Verify authentication token is valid
3. Ensure tracing is enabled (`ENABLE_CONVERSATION_TRACING=true`)
4. Open an issue on GitHub with relevant details

---

**Document Version**: 1.0.0  
**Last Updated**: November 18, 2025  
**Related Documentation**:
- [Conversation Trace Implementation Plan](../CONVERSATION_TRACE_IMPLEMENTATION_PLAN.md)
- [Conversation Trace Implementation Summary](../CONVERSATION_TRACE_IMPLEMENTATION_SUMMARY.md)
- [API Documentation](http://localhost:8000/api/v1/docs)
