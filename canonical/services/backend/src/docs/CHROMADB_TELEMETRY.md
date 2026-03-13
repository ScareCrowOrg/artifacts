---
processed: true
processed_date: 2025-12-08
themes:
  - chromadb
  - telemetry
  - posthog
  - troubleshooting
modules:
  - backend
  - workflows
code_verified: true
dead_docs_found: false
---

# ChromaDB Telemetry and PostHog Integration

## Overview

ChromaDB (version 1.3.5) includes **PostHog** as a direct dependency for anonymous usage telemetry. This telemetry is **enabled by default** and can cause unexpected network calls and potential backend crashes if not properly configured.

## Root Cause Analysis

### The Problem

When the backend performs vector store operations (embedding generation/storage), ChromaDB automatically attempts to send telemetry data to `https://us.i.posthog.com/batch/`. This can cause:

1. **Unexpected external network calls** during embedding operations
2. **Backend crashes** if PostHog initialization or network requests fail
3. **Performance degradation** due to telemetry overhead
4. **Privacy/security concerns** in air-gapped or restricted environments

### Why This Happens

- **ChromaDB 1.3.5** has a dependency: `posthog>=2.4.0,<6.0.0`
- PostHog is a **transitive dependency** (not explicitly declared in our code)
- ChromaDB initializes PostHog telemetry during:
  - `Chroma.from_documents()` calls
  - `Chroma()` client initialization
  - Vector store creation/access operations
- Default behavior: **Telemetry is ENABLED** unless explicitly disabled

### Evidence from Logs

```
2025-12-08 08:05:33,118 - app.workflows.generate_doc_embeddings_and_store - INFO - Vector store path: chroma_db
2025-12-08 08:05:33,118 - app.workflows.generate_doc_embeddings_and_store - INFO - Prepared 24 documents for ingestion
2025-12-08 08:05:33,644 - urllib3.connectionpool - DEBUG - https://us.i.posthog.com:443 "POST /batch/ HTTP/1.1" 200 15
```

The PostHog call happens immediately after document preparation, during the `Chroma.from_documents()` operation in `generate_doc_embeddings_and_store.py` (lines 218-222).

## Solution

### 1. Disable Telemetry (Recommended)

Set the environment variable `ANONYMIZED_TELEMETRY` to `False`:

**`.env` file:**
```bash
ANONYMIZED_TELEMETRY=false
```

**`docker-compose.yml`:**
```yaml
backend:
  environment:
    ANONYMIZED_TELEMETRY: ${ANONYMIZED_TELEMETRY:-False}
```

**`docker-compose.override.yml`:**
```yaml
backend:
  environment:
    ANONYMIZED_TELEMETRY: False
```

**Kubernetes/Kind (ConfigMap):**

The variable is automatically included in the backend ConfigMap when deploying to Kubernetes/Kind:

1. Ensure `ANONYMIZED_TELEMETRY=false` is in your `.env` file (root of repository)
2. Run `make secrets-create-configmaps` to create/update ConfigMaps from .env
3. The `create-configmaps-from-env.sh` script automatically adds it to `backend-config` ConfigMap
4. Backend deployment already references this ConfigMap via `envFrom: configMapRef: backend-config`

Verify the ConfigMap contains the variable:
```bash
kubectl get configmap backend-config -n scareverse-dev -o yaml | grep ANONYMIZED_TELEMETRY
# Should output: ANONYMIZED_TELEMETRY: "false"
```

### 2. Verify Configuration

Check that the correct environment variable is set:

```bash
# In the backend container
echo $ANONYMIZED_TELEMETRY
# Should output: False
```

### 3. Common Mistakes

❌ **Wrong variable name**: `CHROMA_TELEMETRY_ENABLED=false` (does nothing)  
✅ **Correct variable name**: `ANONYMIZED_TELEMETRY=false`

❌ **Case sensitivity**: `anonymized_telemetry=false` (might not work)  
✅ **Use correct case**: `ANONYMIZED_TELEMETRY=false`

## Technical Details

### PostHog Dependency Chain

```
ScareVerse Backend
  └── chromadb==1.3.5
       └── posthog>=2.4.0,<6.0.0
```

### Affected Code Paths

1. **Document Embedding Generation**:
   - File: `backend/app/workflows/generate_doc_embeddings_and_store.py`
   - Function: `store_doc_chunks_in_chromadb()`
   - Lines: 218-232 (Chroma.from_documents() and add_documents())

2. **Code Embedding Generation**:
   - File: `backend/app/workflows/generate_code_embeddings_and_store.py`
   - Similar vector store operations

3. **RAG Service**:
   - File: `backend/app/services/rag/rag_service.py`
   - Any ChromaDB client initialization

### PostHog Telemetry Data

When enabled, ChromaDB sends:
- Anonymous usage statistics
- Feature usage patterns
- Error/crash reports
- Performance metrics

**No sensitive data** (file contents, embeddings, queries) is transmitted.

## Testing the Fix

### 1. Verify Telemetry is Disabled

```bash
# Start the backend with environment variable set
docker-compose up backend

# Check logs - should NOT see posthog.com requests
docker-compose logs backend | grep posthog
# Should return nothing
```

### 2. Monitor Network Calls

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Watch for urllib3 connections
docker-compose logs backend | grep urllib3.connectionpool
# Should not see us.i.posthog.com
```

### 3. Test Vector Store Operations

```python
# Test embedding generation doesn't crash
python backend/app/workflows/generate_doc_embeddings_and_store.py \
  --chunks-json-path /path/to/chunks.json \
  --document-id test-doc
```

## Troubleshooting

### Backend Still Crashes During Embedding Operations

1. **Check environment variable is set**:
   ```bash
   docker-compose exec backend env | grep ANONYMIZED_TELEMETRY
   ```

2. **Restart containers** after changing .env:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. **Check for other network issues**:
   - Ollama connection (`OLLAMA_BASE_URL`)
   - MongoDB connection (`MONGODB_HOST`)
   - Redis connection (`REDIS_HOST`)

### Still Seeing PostHog Calls

1. **Verify ChromaDB version**:
   ```bash
   pip show chromadb
   # Should show 1.3.5
   ```

2. **Check for multiple ChromaDB initializations**:
   ```bash
   grep -r "Chroma(" backend/app/ --include="*.py"
   ```

3. **Ensure environment variable is propagated**:
   - Check `docker-compose.override.yml`
   - Check `.env` file
   - Verify no hardcoded values override the env var

## Alternative Solutions

### Option 1: Code-Level Configuration (Not Recommended)

You can disable telemetry in code, but this is less flexible:

```python
from chromadb.config import Settings

settings = Settings(anonymized_telemetry=False)
client = chromadb.Client(settings)
```

**Why not recommended**: Requires code changes in multiple places, harder to maintain.

### Option 2: Network-Level Blocking

Block `us.i.posthog.com` at firewall/network level. This prevents telemetry but may cause delays or errors if not gracefully handled.

### Option 3: Upgrade ChromaDB (Future)

Monitor ChromaDB releases for versions that:
- Remove PostHog dependency
- Make telemetry opt-in instead of opt-out
- Provide better error handling for telemetry failures

## References

- **ChromaDB Documentation**: https://docs.trychroma.com/
- **PostHog**: https://posthog.com/
- **Issue Report**: Backend Issue - PostHog causing unexpected crashes
- **ChromaDB Source**: https://github.com/chroma-core/chroma

## Related Files

- `backend/requirements.txt` - PostHog dependency documented
- `backend/pyproject.toml` - ChromaDB dependency with telemetry note
- `backend/.env.example` - Environment variable configuration
- `backend/README.md` - Setup instructions with telemetry notice
- `docker-compose.yml` - Production configuration
- `docker-compose.override.yml` - Development configuration

## Change History

- **2025-12-08**: Initial documentation - Root cause analysis and solution
- **2025-12-08**: Fixed incorrect environment variable (`CHROMA_TELEMETRY_ENABLED` → `ANONYMIZED_TELEMETRY`)
- **2025-12-08**: Added error handling in `generate_doc_embeddings_and_store.py`
- **2025-12-08**: Extended fix to Kubernetes/Kind environments - Added ANONYMIZED_TELEMETRY to ConfigMap creation script
