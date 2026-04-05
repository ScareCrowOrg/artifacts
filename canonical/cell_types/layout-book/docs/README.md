---
processed: true
processed_date: 2025-12-20
updated_docs:
  - docs/official/features/workspace/layout-books.md
themes:
  - cell-types
  - artifacts
modules:
  - backend
  - frontend
code_verified: true
dead_docs_found: false
---
# Layout Book Cell Type

## Overview

Layout Books enable users to save, name, and restore complete workspace configurations in the Dynamic Workspace. This feature allows users to preserve their preferred workspace layouts and quickly switch between different working contexts.

## Purpose

- **Save Workspace State**: Capture the current arrangement of cells, their positions, and states
- **Restore Layouts**: Quickly reload saved configurations to resume work
- **Manage Multiple Contexts**: Switch between different workspace arrangements (e.g., "Frontend Development", "Code Review", "Documentation")

## Data Structure

A Layout Book stores:

### Cell References
- **Persistent Cells**: Store only the cell ID reference
- **Ephemeral Cells**: Store full initialization data to recreate the cell

### Grid Configuration
- Column count
- Row height
- Margin settings
- Other grid layout properties

### Cell Positions and States
- X, Y coordinates on the grid
- Width and height
- Minimized/maximized state

### Metadata
- Total cell count
- Count of persistent vs ephemeral cells
- Last applied timestamp
- Creation source

## Usage

Layout Books are managed through the Frontend UI in the FooterWindowManager component:

1. **Save Current Layout**: Click "Save Current Layout" to create a new book from the current workspace
2. **Load Layout Book**: Select a layout book from the dropdown to restore it
3. **Delete Layout Book**: Remove unwanted layout configurations

## API Endpoints

Layout Books are managed through the `/api/v1/layout-books` endpoints:

- `POST /api/v1/layout-books` - Create new layout book
- `GET /api/v1/layout-books` - List user's layout books
- `GET /api/v1/layout-books/{id}` - Get specific layout book
- `PUT /api/v1/layout-books/{id}` - Update layout book
- `DELETE /api/v1/layout-books/{id}` - Delete layout book
- `PUT /api/v1/layout-books/{id}/apply` - Validate before applying

## Technical Implementation

Layout Books leverage the NotebookItemType architecture:
- Type ID: `layout-book`
- Category: `workspace`
- Storage: MongoDB as specialized Book instances
- Schema Version: 1.0.0

## Version History

- **1.0.0** (2025-12-19): Initial implementation
  - Core CRUD operations
  - Persistent and ephemeral cell support
  - Grid configuration preservation
