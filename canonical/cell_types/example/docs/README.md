---
processed: true
processed_date: 2025-12-09
themes:
  - cells
  - plugin-system
  - example
  - documentation
modules:
  - backend
  - frontend
code_verified: true
dead_docs_found: false
---
# Example Cell Type

## Overview

This is a reference implementation of a plug-and-play cell type in ScareVerse. It demonstrates the standard structure and conventions for creating new cell types.

## Purpose

- **Educational**: Serves as a template for creating new cell types
- **Reference**: Shows best practices for cell implementation
- **Testing**: Used to validate the plug-and-play architecture

## Features

- Simple message display and counter
- Demonstrates backend-frontend integration
- Shows proper use of `type.json` references
- Includes comprehensive tests

## Properties

### message (string)
- **Description**: Display message shown in the cell
- **Default**: "Hello from Example Cell"
- **Required**: No

### counter (integer)
- **Description**: Simple counter that can be incremented
- **Default**: 0
- **Required**: No

## Usage

### Creating an Instance

```python
from backend.app.models.content import Cell

cell = Cell(
    notebook_item_type_id="example",
    initial_data={
        "message": "Custom message",
        "counter": 5
    }
)
```

### Frontend Rendering

The cell automatically renders using `frontend/View.vue` when displayed in a notebook.

## Components

- **Backend**: `backend/scripts/main.py` - Simple execution logic
- **Frontend**: `frontend/View.vue` - Vue component for rendering
- **Tests**: Backend and frontend tests included
- **Documentation**: This file

## Development

See [ADDING_NEW_CELL_TYPE.md](../../../docs/official/ADDING_NEW_CELL_TYPE.md) for guidance on creating new cell types based on this example.
