# Cell Types Directory

This directory contains the plug-and-play cell type definitions for the ScareVerse project.

## Overview

Each subdirectory represents a distinct cell type following the modular architecture pattern. Cell types are self-contained units with all necessary components (backend, frontend, docs, tests).

## Structure

Each cell type directory follows this standard structure:

```
{cell_type_id}/
├── type.json              # Cell type definition (required)
├── backend/               # Backend components (optional)
│   ├── workflow.yaml      # LangGraph workflow definition
│   ├── scripts/           # Python scripts
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── utils.py
│   └── tests/             # Backend tests
│       └── test_main.py
├── frontend/              # Frontend components (optional)
│   ├── View.vue           # Vue component for cell rendering
│   ├── composables.js     # Vue composables
│   ├── store.js           # Pinia store
│   └── tests/             # Frontend tests
│       └── View.spec.js
└── docs/                  # Documentation (required)
    └── README.md          # Cell type documentation
```

## Available Cell Types

- **example**: Reference implementation demonstrating the plug-and-play pattern

## Adding a New Cell Type

See [ADDING_NEW_CELL_TYPE.md](../../docs/official/ADDING_NEW_CELL_TYPE.md) for detailed instructions.

## Discovery Mechanism

Cell types are automatically discovered at backend startup by scanning this directory for `type.json` files. The `NotebookItemTypeRegistry` service loads and validates each type.

## Principles

1. **Modular**: Each type is self-contained
2. **Plug and Play**: Add/remove types without code changes
3. **JSON as Reference**: `type.json` references all component files
4. **Isolated**: Components don't interfere with other types
5. **Traceable**: All artifacts referenced from central JSON

## References

- Technical Specification: `docs/issues/949/technical-specification.md`
- Action Plan: `docs/issues/949/action-plan.md`
- RULESET: `docs/official/RULESET.md`
