---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - troubleshooting
  - debugging
  - rag
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Utils Module Troubleshooting Guide

Common issues and solutions for the utils module (RAG, conversation memory, input processing).

## Ollama Issues

### Ollama Not Running

**Symptom:**
```
Error: Could not connect to Ollama at http://localhost:11434
ConnectionError: Failed to connect to Ollama service
```

**Solutions:**

1. **Verify Ollama is installed:**
   ```bash
   ollama --version
   ```
   If not installed, visit [https://ollama.ai/](https://ollama.ai/)

2. **Start Ollama service:**
   ```bash
   ollama serve
   ```

3. **Check it's running:**
   ```bash
   curl http://localhost:11434/api/tags
   ```
   Should return JSON with available models

4. **Check configuration:**
   ```python
   from backend.app.config import OLLAMA_BASE_URL
   print(f"Ollama URL: {OLLAMA_BASE_URL}")
   ```

### Model Not Found

**Symptom:**
```
Error: model 'mistral' not found
```

**Solutions:**

1. **Pull the model:**
   ```bash
   ollama pull mistral
   ```

2. **Verify it's available:**
   ```bash
   ollama list
   ```

3. **Use a different model:**
   ```python
   # In code
   vectorstore = ingest_documents_to_vectorstore(embedding_model='phi')
   
   # Or in .env
   OLLAMA_EMBEDDING_MODEL=phi
   ```

### Model Download Slow

**Symptom:**
Models taking a long time to download

**Solutions:**

1. **Use smaller models:**
   ```bash
   ollama pull phi  # ~2GB instead of mistral's ~4GB
   ```

2. **Check network connection:**
   ```bash
   ping ollama.ai
   ```

3. **Use local mirror (if available in your region)**

## Vector Store Issues

### Vector Store Not Found

**Symptom:**
```
FileNotFoundError: Vector store not found at chroma_db/
RuntimeError: No collection 'scareverse_docs' found
```

**Solutions:**

1. **Run ingestion to create vector store:**
   ```bash
   python ingest.py
   ```

2. **Or in code:**
   ```python
   from backend.app.utils.document_ingestion import ingest_documents_to_vectorstore
   vectorstore = ingest_documents_to_vectorstore()
   ```

3. **Verify vector store was created:**
   ```bash
   ls -la chroma_db/
   ```

### Empty Vector Store

**Symptom:**
No documents found in searches, zero results

**Solutions:**

1. **Check if documents were ingested:**
   ```python
   from backend.app.utils.document_ingestion import get_or_create_vectorstore
   vectorstore = get_or_create_vectorstore()
   
   # Should be > 0
   count = vectorstore._collection.count()
   print(f"Documents in vector store: {count}")
   ```

2. **Re-ingest with force recreate:**
   ```python
   vectorstore = ingest_documents_to_vectorstore(force_recreate=True)
   ```

3. **Check BASE_DIR configuration:**
   ```python
   from backend.app.config import BASE_DIR
   print(f"Base directory: {BASE_DIR}")
   # Should point to your project root
   ```

### Slow Ingestion

**Symptom:**
Document ingestion taking very long (> 1 hour for medium project)

**Solutions:**

1. **Use a faster model:**
   ```python
   vectorstore = ingest_documents_to_vectorstore(embedding_model='phi')
   ```
   Phi is 2-3x faster than mistral

2. **Reduce chunk size (fewer chunks to process):**
   ```bash
   # In .env
   CHUNK_SIZE=2000
   CHUNK_OVERLAP=100
   ```

3. **Use incremental ingestion:**
   ```python
   # Don't use force_recreate unless necessary
   vectorstore = ingest_documents_to_vectorstore()  # Only processes new files
   ```

4. **Exclude large directories:**
   Add to `.gitignore` or modify ingestion logic to skip:
   - `node_modules/`
   - `venv/`
   - `.git/`
   - `__pycache__/`

### Switching Embedding Models

**Symptom:**
Poor search results after changing embedding model

**Solution:**
**MUST recreate vector store** when switching models:

```python
# Embeddings from different models are NOT compatible
vectorstore = ingest_documents_to_vectorstore(
    embedding_model='phi',
    force_recreate=True  # REQUIRED when changing models
)
```

## RAG / Search Issues

### No Context Retrieved

**Symptom:**
```python
msg, docs = process_user_input(...)
len(docs) == 0  # No context found!
```

**Solutions:**

1. **Check vector store exists:**
   ```python
   from backend.app.utils.document_ingestion import get_or_create_vectorstore
   vectorstore = get_or_create_vectorstore()
   ```

2. **Verify documents are ingested:**
   ```python
   count = vectorstore._collection.count()
   print(f"Documents: {count}")  # Should be > 0
   ```

3. **Try more general query terms:**
   ```python
   # Instead of very specific:
   query = "authentication OAuth2 JWT tokens"
   
   # Try broader:
   query = "authentication"
   ```

4. **Increase k value:**
   ```python
   msg, docs = process_user_input(
       user_message="...",
       vectorstore=vectorstore,
       k=10  # Try higher k
   )
   ```

### Context Not Relevant

**Symptom:**
Retrieved context doesn't match the query well

**Solutions:**

1. **Re-ingest with better model:**
   ```python
   # mistral provides better quality embeddings than phi
   ingest_documents_to_vectorstore(
       embedding_model='mistral',
       force_recreate=True
   )
   ```

2. **Use file references for precision:**
   ```python
   # Instead of: "How does auth work?"
   # Use: "Explain #backend/app/auth.py"
   ```

3. **Adjust chunking parameters:**
   ```bash
   # In .env - Larger chunks = more context per chunk
   CHUNK_SIZE=1500
   CHUNK_OVERLAP=300
   ```

4. **Check if documents need re-ingestion:**
   ```bash
   # If code changed recently, re-ingest
   python ingest.py
   ```

### File Reference Not Found

**Symptom:**
```
Error: Referenced file #docs/MISSING.md not found
FileNotFoundError: docs/MISSING.md
```

**Solutions:**

1. **Verify file exists:**
   ```bash
   ls -la docs/MISSING.md
   ```

2. **Check path is relative to project root:**
   ```python
   # Correct:
   msg = "Check #backend/app/config.py"
   
   # Incorrect:
   msg = "Check #/absolute/path/config.py"
   ```

3. **Ensure file was ingested:**
   ```bash
   python ingest.py
   ```

4. **Check file extension is supported:**
   - Supported: `.md`, `.py`, `.js`, `.txt`, `.json`, etc.
   - Not supported: `.exe`, `.dll`, `.bin`, etc.

## Memory Issues

### Memory Not Persisting

**Symptom:**
Conversation context is lost between requests

**Cause:**
Session ID not being passed consistently

**Solutions:**

1. **Ensure consistent session IDs:**
   ```python
   # Pass session_id in each request
   session_id = request.headers.get('X-Session-ID')
   memory = get_session_memory(session_id)
   ```

2. **Verify session is being reused:**
   ```python
   store = get_session_store()
   count = store.get_active_session_count()
   print(f"Active sessions: {count}")
   ```

3. **Check session isn't being cleared:**
   ```python
   # Avoid calling clear_history() accidentally
   memory = get_session_memory(session_id)
   # Don't do: memory.clear_history()
   ```

### Summarization Not Working

**Symptom:**
Conversation history grows indefinitely without summarization

**Solutions:**

1. **Check Ollama is running:**
   ```bash
   ollama serve
   curl http://localhost:11434/api/tags
   ```

2. **Lower the token limit:**
   ```python
   memory = ConversationMemoryManager(max_token_limit=2000)
   ```

3. **Verify model works:**
   ```bash
   ollama run mistral "Summarize: The user asked about auth."
   ```

4. **Check for errors in logs:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   # Check for summarization errors
   ```

### Memory Token Limit Exceeded

**Symptom:**
Conversations getting slow or failing with long history

**Solutions:**

1. **Reduce max_token_limit:**
   ```python
   memory = ConversationMemoryManager(max_token_limit=2000)
   ```

2. **Clear session periodically:**
   ```python
   # After major topic change
   memory.clear_history()
   ```

3. **Implement session timeout:**
   ```python
   # Clear sessions after 24 hours of inactivity
   store = get_session_store()
   store.cleanup_inactive_sessions(max_age_seconds=86400)
   ```

## Configuration Issues

### Settings Not Applied

**Symptom:**
Changes to `.env` file not taking effect

**Solutions:**

1. **Verify `.env` file location:**
   ```bash
   ls -la .env
   # Should be in project root
   ```

2. **Restart the backend server:**
   ```bash
   # Configuration is loaded at startup
   pkill -f "python.*main.py"
   python -m backend.app.main
   ```

3. **Verify configuration loaded:**
   ```python
   from backend.app.config import (
       OLLAMA_EMBEDDING_MODEL,
       OLLAMA_BASE_URL,
       CHUNK_SIZE
   )
   print(f"Model: {OLLAMA_EMBEDDING_MODEL}")
   print(f"URL: {OLLAMA_BASE_URL}")
   print(f"Chunk size: {CHUNK_SIZE}")
   ```

4. **Check for typos in variable names:**
   ```bash
   # In .env, correct spelling:
   OLLAMA_BASE_URL=http://localhost:11434
   
   # Incorrect:
   OLAMA_BASE_URL=...  # Missing 'L'
   ```

### ChromaDB Permission Errors

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: 'chroma_db/'
```

**Solutions:**

1. **Check directory permissions:**
   ```bash
   ls -ld chroma_db/
   chmod 755 chroma_db/
   ```

2. **Run with correct user:**
   ```bash
   # If running as different user, may need sudo or chown
   sudo chown -R $USER:$USER chroma_db/
   ```

3. **Use different directory:**
   ```bash
   # In .env
   VECTORSTORE_PATH=/tmp/chroma_db
   ```

## Performance Issues

### High Memory Usage

**Symptom:**
Backend process using excessive RAM

**Solutions:**

1. **Reduce token limits:**
   ```python
   memory = ConversationMemoryManager(max_token_limit=2000)
   ```

2. **Clear inactive sessions:**
   ```python
   store = get_session_store()
   store.clear_all_sessions()
   ```

3. **Reduce RAG k value:**
   ```python
   # Instead of k=10
   process_user_input(vectorstore=vs, k=5)
   ```

4. **Use smaller embedding model:**
   ```bash
   # phi uses less memory than mistral
   OLLAMA_EMBEDDING_MODEL=phi
   ```

### Slow Response Times

**Symptom:**
RAG queries or memory operations taking too long

**Solutions:**

1. **Use faster Ollama model:**
   ```bash
   OLLAMA_EMBEDDING_MODEL=phi
   ```

2. **Reduce k (fewer documents retrieved):**
   ```python
   process_user_input(k=3)  # Instead of k=10
   ```

3. **Optimize chunk size:**
   ```bash
   # Larger chunks = fewer total chunks = faster search
   CHUNK_SIZE=2000
   ```

4. **Check Ollama performance:**
   ```bash
   ollama run mistral "Hello"  # Should respond in < 2 seconds
   ```

## Need More Help?

If you're still experiencing issues:

1. **Check logs:**
   ```bash
   tail -f backend.log
   ```

2. **Enable debug mode:**
   ```bash
   export LOG_LEVEL=DEBUG
   python -m backend.app.main
   ```

3. **Run tests:**
   ```bash
   pytest tests/unit/test_document_ingestion.py -v
   pytest tests/unit/test_conversation_memory.py -v
   ```

4. **Review related documentation:**
   - [Document Ingestion](./DOCUMENT_INGESTION.md)
   - [Input Processor](./INPUT_PROCESSOR.md)
   - [Conversation Memory](./CONVERSATION_MEMORY.md)
   - [Main README](./README.md)

5. **Check project issues:**
   - GitHub Issues: https://github.com/ScareCrowOrg/ScareVerseLab/issues
   - Search for similar problems

6. **Open a new issue:**
   Include:
   - Error message (full stack trace)
   - Steps to reproduce
   - Environment details (OS, Python version, Ollama version)
   - Configuration (anonymize sensitive data)