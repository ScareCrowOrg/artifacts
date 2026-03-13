---
issue: PostHog telemetry causing backend crash
date: 2025-12-08
status: resolved
severity: high
category: bug-fix
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - analytics
  - incident
modules:
  - backend
code_verified: true
dead_docs_found: false
---


# Executive Summary: PostHog Telemetry Issue Resolution

## Problem Statement

The backend service was experiencing unexpected crashes during vector store operations (document embedding generation). Investigation revealed unauthorized network calls to `https://us.i.posthog.com/batch/` despite no explicit PostHog usage in the codebase.

## Root Cause

**ChromaDB 1.3.5** includes PostHog as a transitive dependency for anonymous usage telemetry:
- Dependency chain: `ScareVerse Backend → chromadb==1.3.5 → posthog>=2.4.0,<6.0.0`
- Telemetry is **enabled by default** in ChromaDB
- Configuration had **wrong environment variable** (`CHROMA_TELEMETRY_ENABLED` instead of `ANONYMIZED_TELEMETRY`)
- Network failures or exceptions during PostHog initialization caused backend crashes

## Impact

- **Severity**: High
- **Scope**: All vector store operations (RAG embeddings)
- **Affected Files**: 
  - `app/workflows/generate_doc_embeddings_and_store.py`
  - `app/workflows/generate_code_embeddings_and_store.py`
  - `app/services/rag/*` (any ChromaDB usage)

## Solution Implemented

### 1. Configuration Fixes

**File**: `docker-compose.override.yml`
```diff
- CHROMA_TELEMETRY_ENABLED: false
+ ANONYMIZED_TELEMETRY: False
```

**File**: `docker-compose.yml`
```diff
  MONGODB_PASSWORD: ${MONGODB_PASSWORD:-scareverse-dev-password}
+ ANONYMIZED_TELEMETRY: ${ANONYMIZED_TELEMETRY:-False}
```

**File**: `.env.example`
```bash
# ChromaDB Telemetry Configuration
# ChromaDB uses PostHog for anonymous usage telemetry by default
# Set to False to disable telemetry and prevent external network calls to posthog.com
ANONYMIZED_TELEMETRY=false
```

### 2. Code Improvements

**File**: `app/workflows/generate_doc_embeddings_and_store.py`

Added exception handling around ChromaDB operations:
```python
try:
    Chroma.from_documents(...)
except Exception as e:
    logger.error(f"Error during vector store operation: {e}")
    logger.warning("This might be due to ChromaDB telemetry. Ensure ANONYMIZED_TELEMETRY=false is set.")
    raise
```

### 3. Documentation

**New Files**:
- `backend/docs/CHROMADB_TELEMETRY.md` - Comprehensive troubleshooting guide
- `backend/test_chromadb_telemetry.py` - Verification script

**Updated Files**:
- `backend/README.md` - Added telemetry warning in setup section
- `backend/requirements.txt` - Documented PostHog transitive dependency
- `backend/pyproject.toml` - Added comments explaining telemetry

## Verification Steps

### Environment Variable Check
```bash
# In backend container
echo $ANONYMIZED_TELEMETRY
# Expected: False
```

### Log Monitoring
```bash
# Should NOT see posthog.com in logs
docker-compose logs backend | grep posthog
# Expected: no output
```

### Run Verification Script
```bash
cd backend
export ANONYMIZED_TELEMETRY=false
python test_chromadb_telemetry.py
# Expected: All tests pass
```

## Files Changed

### Configuration
- `docker-compose.yml` - Added ANONYMIZED_TELEMETRY environment variable
- `docker-compose.override.yml` - Fixed environment variable name
- `backend/.env.example` - Added telemetry configuration section
- `.env.example` (root) - Added ANONYMIZED_TELEMETRY in RAG configuration section
- `infrastructure/local/scripts/create-configmaps-from-env.sh` - Added ANONYMIZED_TELEMETRY as backend-only variable

### Code
- `backend/app/workflows/generate_doc_embeddings_and_store.py` - Added error handling

### Documentation
- `backend/README.md` - Added telemetry warning and documentation link
- `backend/requirements.txt` - Added comments for chromadb and posthog
- `backend/pyproject.toml` - Added comments for chromadb and posthog
- `backend/docs/CHROMADB_TELEMETRY.md` - Comprehensive guide (updated with Kubernetes instructions)
- `backend/test_chromadb_telemetry.py` - Verification script

## Extension to Kubernetes/Kind

### Changes for Kind/Kubernetes Deployment

The telemetry fix has been extended to support Kubernetes/Kind environments:

1. **Root `.env.example`**: Added `ANONYMIZED_TELEMETRY=false` to the RAG and Vector Store Configuration section
2. **ConfigMap Script**: Updated `infrastructure/local/scripts/create-configmaps-from-env.sh` to classify `ANONYMIZED_TELEMETRY` as a backend-only variable
3. **Automatic Propagation**: When `make secrets-create-configmaps` is run, the variable is automatically added to the `backend-config` ConfigMap
4. **Backend Integration**: Existing backend deployment already consumes the ConfigMap via `envFrom`, no deployment changes needed

### Verification for Kubernetes

```bash
# After deploying to Kind cluster
kubectl get configmap backend-config -n scareverse-dev -o yaml | grep ANONYMIZED_TELEMETRY
# Expected: ANONYMIZED_TELEMETRY: "false"

# Check backend pod has the variable
kubectl exec -n scareverse-dev deployment/backend -- env | grep ANONYMIZED_TELEMETRY
# Expected: ANONYMIZED_TELEMETRY=false
```

## Testing Recommendations

1. **Unit Tests**: Verify ChromaDB can initialize without network calls
2. **Integration Tests**: Run full embedding generation workflow
3. **Monitoring**: Watch for posthog.com in network logs
4. **Performance**: Measure latency improvement without telemetry

## Preventive Measures

1. **Dependency Audits**: Regular review of transitive dependencies
2. **Network Monitoring**: Alert on unexpected external network calls
3. **Environment Variable Validation**: Startup checks for critical configuration
4. **Documentation**: Keep telemetry documentation updated with ChromaDB versions

## Next Steps

- [ ] Deploy to test environment
- [ ] Verify no PostHog calls in logs
- [ ] Monitor backend stability during vector operations
- [ ] Update runbooks with telemetry troubleshooting steps
- [ ] Consider upgrading ChromaDB when telemetry becomes opt-in

## Related Issues

- Backend crash during embedding generation
- Unexpected network calls to external services
- Vector store initialization failures

## References

- ChromaDB Documentation: https://docs.trychroma.com/
- PostHog: https://posthog.com/
- Issue: [backend] Análise profunda do PostHog: chamada inesperada e crash do serviço
- PR: copilot/verbal-guineafowl

---

**Author**: GitHub Copilot Agent  
**Date**: 2025-12-08  
**Status**: Implementation Complete, Pending Production Validation
