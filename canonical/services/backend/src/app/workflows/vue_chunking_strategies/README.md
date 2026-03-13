---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - workflows
  - chunking
  - vue
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Vue.js Chunking Strategies Module

Intelligent chunking strategies for Vue.js ecosystem files in RAG ingestion.

## Overview

This module provides specialized chunking strategies for Vue.js Single File Components (.vue), JavaScript, and TypeScript files, optimized for dual collection ingestion (code and documentation).

## Directory Structure

```
vue_chunking_strategies/
├── README.md                      # This file
├── __init__.py                   # Public API exports (31 lines)
├── vue_chunking_orchestrator.py  # Main entry point (82 lines)
├── vue_sfc_chunker.py            # Vue SFC parsing (193 lines)
└── vue_javascript_chunker.py     # JavaScript/TypeScript chunking (329 lines)
```

## Components

### Vue Chunking Orchestrator (`vue_chunking_orchestrator.py`)

**Purpose**: Main entry point that dispatches to appropriate chunking strategies based on file type.

**Function**:
- `chunk_vue_code()`: Main chunking dispatcher

**Strategy**:
- Routes `.vue` files to Vue SFC chunker
- Routes `.js`/`.ts` files to JavaScript chunker
- Returns dual lists: code chunks and documentation chunks

**Usage**:
```python
from app.workflows.vue_chunking_strategies import chunk_vue_code

code_chunks, doc_chunks = chunk_vue_code(
    content="<template>...</template>...",
    file_path=Path("components/ChatIA.vue"),
    document_id="vue-001",
    file_type="vue"
)
```

### Vue SFC Chunker (`vue_sfc_chunker.py`)

**Purpose**: Parse and chunk Vue Single File Components.

**Functions**:
- `chunk_vue_sfc()`: Parse and chunk Vue SFC into blocks
- `extract_vue_blocks()`: Extract `<template>`, `<script>`, `<style>` blocks

**Strategy**:
- Extracts `<template>` block for HTML/Tailwind CSS
- Extracts `<script>` or `<script setup>` block (detects `lang="ts"`)
- Extracts `<style>` block (detects `lang="scss"`, `scoped` attribute)
- Further processes script block to extract functions and JSDoc

**Returns**:
- Template chunks for code collection
- Script chunks with extracted functions
- Style chunks for code collection
- JSDoc chunks for documentation collection

**Usage**:
```python
from app.workflows.vue_chunking_strategies import chunk_vue_sfc

code_chunks, doc_chunks = chunk_vue_sfc(
    content="<template>...</template><script setup>...</script>",
    file_path=Path("components/ChatIA.vue"),
    document_id="vue-001"
)
```

### Vue JavaScript Chunker (`vue_javascript_chunker.py`)

**Purpose**: Extract functions, composables, Pinia stores, and JSDoc from JavaScript/TypeScript files.

**Functions**:
- `chunk_javascript_file()`: Main chunking function
- `infer_js_chunk_type()`: Infer chunk type from file path
- `extract_code_and_comments()`: Extract code units and JSDoc
- `extract_function_body()`: Helper to extract complete function bodies
- `find_preceding_jsdoc()`: Associate JSDoc with functions

**Strategy**:
- Detects file type from path:
  - `composables/` → `vue_composable`
  - `stores/` → `vue_pinia_store`
  - `components/` → `vue_component_script`
- Extracts exported functions using regex patterns:
  - `export function functionName(...) { ... }`
  - `export const functionName = (...) => { ... }`
  - `export const useStore = defineStore(...)`
- Extracts JSDoc blocks and associates them with functions
- Separates standalone JSDoc for documentation collection

**Usage**:
```python
from app.workflows.vue_chunking_strategies import chunk_javascript_file

code_chunks, doc_chunks = chunk_javascript_file(
    content="export function useChat() {...}",
    file_path=Path("composables/useChat.js"),
    document_id="js-001",
    file_type="js"
)
```

## Chunk Metadata

All chunks include rich metadata:

```python
{
    "content": "...",
    "metadata": {
        "document_id": "unique-id",
        "source": "/path/to/file",
        "file_type": "vue|javascript",
        "chunk_type": "vue_template|vue_script_js|vue_composable_function|...",
        "char_count": 1234,
        "embedding_model_id": "deepseek-coder|mistral",
        "target_collection": "scareverse_code|scareverse_docs",
        # Additional type-specific metadata
        "function_name": "useChat",  # For JS functions
        "has_jsdoc": true,            # For code chunks
        "script_lang": "ts",          # For Vue scripts
        "style_lang": "scss"          # For Vue styles
    }
}
```

## Target Collections

### scareverse_code (Source Code)
- **Embedding Model**: `deepseek-coder`
- **Content Types**:
  - Vue templates (`<template>`)
  - Vue scripts (`<script>`, `<script setup>`)
  - Vue styles (`<style>`)
  - JavaScript/TypeScript functions
  - Pinia store definitions
  - Composables
- **Use Case**: Code snippet retrieval, component discovery

### scareverse_docs (Documentation)
- **Embedding Model**: `mistral`
- **Content Types**:
  - JSDoc comments
  - Function documentation
  - Component documentation
- **Use Case**: Natural language documentation search

## Dual Collection Ingestion

This module is designed for **dual collection ingestion**:

1. **Code Chunks** → `scareverse_code` collection (deepseek-coder embeddings)
2. **Doc Chunks** → `scareverse_docs` collection (mistral embeddings)

This allows:
- Semantic code search for finding similar code patterns
- Natural language search for finding documented functionality
- Cross-referencing code and documentation

## Backward Compatibility

The original `vue_chunking_strategies.py` will be converted to a shim that re-exports all functions:

```python
# Old import (still works)
from app.workflows.vue_chunking_strategies import chunk_vue_code

# New recommended import (same result)
from app.workflows.vue_chunking_strategies import chunk_vue_code
```

## RULESET.md Compliance

| Rule | Requirement | Status |
|------|-------------|--------|
| **Rule 1.1** | File Size < 500 lines | ✅ All files under 330 lines |
| **Rule 1.3** | Descriptive file names | ✅ `vue_sfc_chunker`, `vue_javascript_chunker`, `vue_chunking_orchestrator` |
| **Rule 2.1** | README.md in directories | ✅ This file |
| **Rule 4.3** | Technical naming in English | ✅ All names in English |

## Line Counts

```
✓ PASS: __init__.py has 31 lines
✓ PASS: vue_chunking_orchestrator.py has 82 lines
✓ PASS: vue_sfc_chunker.py has 193 lines
✓ PASS: vue_javascript_chunker.py has 329 lines
```

**Total reduction**: 546 lines → **41 lines** (shim) + **635 lines** (modularized)

## Testing

Tests are located in:
- `backend/tests/unit/backend/test_vue_chunking_strategies.py`
- `backend/tests/unit/backend/workflows/test_vue_chunking_strategies.py`

All existing tests remain compatible due to backward-compatible exports.

## Example: Chunking a Vue SFC

```javascript
// components/ChatMessage.vue
<template>
  <div class="message">{{ content }}</div>
</template>

<script setup lang="ts">
/**
 * Chat message component
 * Displays a single message in the chat
 */
export interface Props {
  content: string
}

const props = defineProps<Props>()
</script>

<style scoped lang="scss">
.message {
  padding: 1rem;
  border-radius: 0.5rem;
}
</style>
```

**Result**:
- **3 code chunks** (template, script, style) → scareverse_code
- **1 doc chunk** (JSDoc comment) → scareverse_docs

## Related Documentation

- [Workflows README](../README.md) - Parent module documentation
- [Chunking Strategies](../chunking_strategies/) - General chunking strategies
- [Ingestion Graph](../ingestion_graph.py) - Uses these chunking strategies
- [RAG Architecture](../../docs/rag/) - RAG system architecture
