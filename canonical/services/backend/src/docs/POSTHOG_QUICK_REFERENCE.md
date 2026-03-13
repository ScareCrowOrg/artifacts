---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - analytics
  - posthog
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# PostHog Telemetry Issue - Quick Reference Guide

## Problem
Backend crashes during vector store operations due to ChromaDB's PostHog telemetry.

## Root Cause
- ChromaDB 1.3.5 includes PostHog for anonymous telemetry (enabled by default)
- Wrong environment variable configured: `CHROMA_TELEMETRY_ENABLED=false` (ineffective)
- Network failures during telemetry caused unhandled exceptions

## Solution (TL;DR)

### 1. Fix Environment Variable
```bash
# In .env file
ANONYMIZED_TELEMETRY=false
```

### 2. Already Fixed In
- ✅ `docker-compose.yml` (line 39)
- ✅ `docker-compose.override.yml` (line 92)
- ✅ `.env.example` (lines 114-117)

### 3. Verify Fix
```bash
# In backend directory
export ANONYMIZED_TELEMETRY=false
python test_chromadb_telemetry.py
```

## Expected Result
- ✅ No network calls to `posthog.com`
- ✅ No backend crashes during embedding operations
- ✅ Vector store operations complete successfully

## Quick Troubleshooting

### Check Environment Variable
```bash
docker-compose exec backend env | grep ANONYMIZED_TELEMETRY
# Should output: ANONYMIZED_TELEMETRY=false
```

### Check Logs for PostHog
```bash
docker-compose logs backend | grep posthog
# Should output: nothing
```

### If Still Crashing
1. Restart containers: `docker-compose down && docker-compose up -d`
2. Check other network issues (Ollama, MongoDB, Redis)
3. Review full logs: `docker-compose logs backend --tail=100`

## Documentation

- **Complete Guide**: `backend/docs/CHROMADB_TELEMETRY.md`
- **Executive Summary**: `backend/docs/POSTHOG_INCIDENT_SUMMARY.md`
- **Verification Script**: `backend/test_chromadb_telemetry.py`

## Files Modified (Summary)

| File | Change |
|------|--------|
| `docker-compose.yml` | Added ANONYMIZED_TELEMETRY env var |
| `docker-compose.override.yml` | Fixed env var name |
| `.env.example` | Added telemetry configuration |
| `generate_doc_embeddings_and_store.py` | Added error handling |
| `requirements.txt` | Documented PostHog dependency |
| `pyproject.toml` | Documented ChromaDB telemetry |
| `README.md` | Added setup warning |

## Status
✅ **RESOLVED** - Ready for production deployment

---
Last Updated: 2025-12-08  
Resolution: GitHub Copilot Agent
