---
processed: true
processed_date: 2025-12-09
themes:
  - testing
  - unit-tests
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Backend Unit Tests - File Processors

## Overview

Unit tests for file processing modules including content minimizers, segmenters, and token counters.

## Files Tested

File processors in `app/file_processors/`:
- `content_minimizer.py` - Content minimization logic
- `file_segmenter.py` - File segmentation
- `message_builder.py` - Message construction
- `token_counter.py` - Token counting
- And more...

## Running Tests

```bash
cd backend
pytest tests/unit/backend/file_processors/ -v
```

## Test Coverage

- File processing logic
- Content transformation
- Token calculation
- Edge cases (empty files, large files)
- Error handling

---

For more details, see [Backend Tests README](../../README.md)
