---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - rag
  - priority-context
  - file-references
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Input Processor - Priority-Based RAG

This document details the input processor that implements priority-based context retrieval for RAG (Retrieval Augmented Generation).

## Overview

The input processor implements a 3-tier priority system that intelligently combines different context sources to provide the most relevant information to the LLM.

## Priority System

The input processor uses a **3-tier priority system** for RAG context:

1. **Priority 1: Attached Files** (highest) - Files explicitly attached by the user via UI
2. **Priority 2: File References** - Files referenced in the message with `#path/to/file.ext` syntax
3. **Priority 3: General RAG** - Semantic similarity search across all documents in vector store

This ensures the most relevant context is always prioritized.

## Features

- Automatic file reference extraction from user messages (`#path/to/file.ext` syntax)
- File content loading with encoding fallback (UTF-8, latin-1, cp1252)
- RAG search with ChromaDB similarity search
- Context document formatting optimized for LLM prompts
- Priority-based context merging
- Metadata preservation for context sources

## Usage

### Basic Usage

```python
from backend.app.utils.input_processor import process_user_input
from backend.app.utils.document_ingestion import get_or_create_vectorstore

# Load vectorstore
vectorstore = get_or_create_vectorstore()

# Process user input (automatic priority detection)
processed_msg, context_docs = process_user_input(
    user_message="Tell me about the architecture",
    vectorstore=vectorstore,
    k=5  # Number of chunks to retrieve from RAG
)

# Use processed_msg and context_docs in your LLM prompt
```

### Priority 1: Attached Files

Files explicitly attached by the user take highest priority:

```python
# Files attached from UI
attached_files = [
    {
        'path': 'reports/quarterly_report.pdf',
        'content': '... extracted PDF text ...'
    },
    {
        'path': 'data/analysis.csv',
        'content': '... CSV data ...'
    }
]

processed_msg, context_docs = process_user_input(
    user_message="Analyze this report and compare with the data",
    attached_files=attached_files,
    vectorstore=vectorstore,
    k=5  # Additional RAG context if needed
)

# context_docs will include attached files FIRST
# followed by RAG results if k > len(attached_files)
```

### Priority 2: File References

Reference specific files using `#` syntax:

```python
processed_msg, context_docs = process_user_input(
    user_message="Check #docs/README.md and #backend/app/config.py for setup",
    vectorstore=vectorstore,
    k=5
)

# The processor will:
# 1. Extract: ['docs/README.md', 'backend/app/config.py']
# 2. Load file contents from filesystem
# 3. Search vector store for relevant chunks from those files
# 4. Remove #-references from processed_msg
```

**File Reference Syntax:**
- `#docs/README.md` - References README in docs directory
- `#backend/app/config.py` - References config file
- `#docs/ARCHITECTURE.md` - References architecture doc
- `#relative/path/to/file.ext` - Any relative path from project root

**What happens to file references:**
- Extracted from message
- Used for targeted RAG search
- **Removed from the final message** sent to LLM (to avoid confusion)

### Priority 3: General RAG

When no attached files or references are provided:

```python
processed_msg, context_docs = process_user_input(
    user_message="Explain how authentication works",
    vectorstore=vectorstore,
    k=5  # Semantic search for top 5 relevant chunks
)

# Performs similarity search across entire vector store
```

## Context Formatting

### Format Context for LLM Prompts

```python
from backend.app.utils.input_processor import format_context_for_prompt

# Format retrieved context for LLM
context_str = format_context_for_prompt(context_docs)

# Build full prompt
full_prompt = f"""Context:
{context_str}

User Question: {processed_msg}

Please answer based on the context provided above.
"""
```

**Output format:**

```
--- Context 1 (Source: backend/app/main.py) ---
[Content of chunk 1...]

--- Context 2 (Source: docs/ARCHITECTURE.md) ---
[Content of chunk 2...]

--- Context 3 (Source: backend/app/config.py) ---
[Content of chunk 3...]
```

## Priority Merging Logic

The processor intelligently merges contexts from different priorities:

```python
# Example with all three priorities:
attached_files = [{'path': 'report.pdf', 'content': '...'}]  # Priority 1
user_message = "Compare with #data/baseline.csv"              # Priority 2 reference
# + general RAG                                               # Priority 3

processed_msg, context_docs = process_user_input(
    user_message=user_message,
    attached_files=attached_files,
    vectorstore=vectorstore,
    k=5
)

# Resulting context_docs order:
# 1. Attached files (report.pdf)
# 2. Referenced files (data/baseline.csv chunks)
# 3. General RAG results (if k > combined count from 1+2)
```

This ensures:
- User-provided context always takes precedence
- Explicit file references are honored
- General RAG fills in remaining slots

## Advanced Features

### File Content Loading

The processor handles file loading with robust error handling:

```python
# Automatically tries multiple encodings:
# 1. UTF-8 (most common)
# 2. latin-1 (ISO-8859-1)
# 3. cp1252 (Windows encoding)

# If all fail, returns error message
# Example: "Error: Could not read file docs/README.md"
```

### Metadata Preservation

Context documents preserve useful metadata:

```python
for doc in context_docs:
    print(f"Source: {doc.metadata['source']}")
    print(f"Type: {doc.metadata.get('file_type', 'unknown')}")
    print(f"Priority: {doc.metadata.get('priority', 3)}")
    print(f"Content: {doc.page_content[:200]}...")
```

### Custom k Values

Adjust the number of retrieved chunks:

```python
# Get more context (useful for complex queries)
processed_msg, context_docs = process_user_input(
    user_message="Explain the entire authentication flow",
    vectorstore=vectorstore,
    k=10  # Retrieve 10 chunks
)

# Get less context (useful for simple queries)
processed_msg, context_docs = process_user_input(
    user_message="What port does the server use?",
    vectorstore=vectorstore,
    k=2  # Only 2 chunks needed
)
```

## Integration Examples

### With Orchestrator

```python
from backend.app.orchestrator import ChatOrchestrator
from backend.app.utils.input_processor import process_user_input
from backend.app.utils.document_ingestion import get_or_create_vectorstore

orchestrator = ChatOrchestrator()
vectorstore = get_or_create_vectorstore()

# Process input with RAG
processed_msg, context_docs = process_user_input(
    user_message=user_message,
    attached_files=attached_files,  # From UI
    vectorstore=vectorstore,
    k=5
)

# Pass to orchestrator
result = orchestrator.process(
    mensagem=processed_msg,
    context_docs=context_docs,  # Inject RAG context
    responsavel_id=user_id,
    modelo="mistral"
)
```

### With Direct LLM Call

```python
from backend.app.services.ollama_service import processar_chat_com_ollama
from backend.app.utils.input_processor import (
    process_user_input,
    format_context_for_prompt
)

# Get context
processed_msg, context_docs = process_user_input(
    user_message="How do I deploy this?",
    vectorstore=vectorstore,
    k=5
)

# Format for prompt
context_str = format_context_for_prompt(context_docs)

# Build prompt
prompt = f"""Context:
{context_str}

User Question: {processed_msg}

Answer:"""

# Call LLM
response = await processar_chat_com_ollama(
    nova_intencao=prompt,
    model="mistral"
)
```

## Testing

```python
# Test Priority 1: Attached files
def test_priority_1_attached_files():
    attached = [{'path': 'test.txt', 'content': 'Test content'}]
    msg, docs = process_user_input(
        user_message="Analyze this",
        attached_files=attached,
        vectorstore=vectorstore,
        k=5
    )
    assert len(docs) >= 1
    assert docs[0].page_content == 'Test content'

# Test Priority 2: File references
def test_priority_2_file_references():
    msg, docs = process_user_input(
        user_message="Check #README.md for details",
        vectorstore=vectorstore,
        k=5
    )
    assert '#README.md' not in msg  # Should be removed
    assert any('README.md' in doc.metadata['source'] for doc in docs)

# Test Priority 3: General RAG
def test_priority_3_general_rag():
    msg, docs = process_user_input(
        user_message="How does authentication work?",
        vectorstore=vectorstore,
        k=5
    )
    assert len(docs) == 5
    assert msg == "How does authentication work?"  # Unchanged
```

## Performance Tips

1. **Adjust k based on query complexity**:
   - Simple queries: k=2-3
   - Complex queries: k=7-10
   - Very complex: k=15-20

2. **Use file references for targeted queries**:
   ```python
   # More efficient than general RAG
   msg = "Explain #backend/app/auth.py authentication logic"
   ```

3. **Pre-load frequently accessed files**:
   ```python
   # Cache common files as attached_files for faster access
   common_files = load_common_docs()
   ```

## Troubleshooting

### File Reference Not Found

```
Error: Referenced file #docs/MISSING.md not found
```

**Solution:**
- Verify file exists in project
- Check path is relative to project root
- Ensure file was ingested: `python ingest.py`

### No Context Retrieved

```python
msg, docs = process_user_input(...)
assert len(docs) == 0  # No context found!
```

**Solutions:**
1. Check vector store exists: `get_or_create_vectorstore()`
2. Verify documents are ingested: `python ingest.py`
3. Try more general query terms
4. Increase k value: `k=10` instead of `k=5`

### Context Not Relevant

If retrieved context doesn't match query:

1. **Re-ingest with better model**:
   ```python
   ingest_documents_to_vectorstore(
       embedding_model='mistral',  # Better quality
       force_recreate=True
   )
   ```

2. **Use file references for precision**:
   ```python
   # Instead of: "How does auth work?"
   # Use: "Explain #backend/app/auth.py"
   ```

3. **Adjust chunking parameters**:
   ```bash
   # In .env
   CHUNK_SIZE=1500  # Larger chunks = more context per chunk
   CHUNK_OVERLAP=300
   ```

## Related Documentation

- [Document Ingestion](./DOCUMENT_INGESTION.md) - How to build the vector store
- [Conversation Memory](./CONVERSATION_MEMORY.md) - Managing conversation context
- [Main README](./README.md) - Utils module overview
- [RAG Service](../services/README.md) - High-level RAG service
