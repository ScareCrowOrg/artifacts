---
processed: true
processed_date: 2025-12-20
updated_docs:
  - docs/official/features/workspace/layout-books.md
themes:
  - api
  - backend
  - rest
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Layout Books API

## Overview

The Layout Books API enables users to save, manage, and restore complete workspace configurations in the Dynamic Workspace. This includes cell positions, grid settings, and initialization data for both persistent and ephemeral cells.

## Base Path

All Layout Books endpoints are prefixed with `/api/v1/layout-books`

## Authentication

All endpoints require authentication via JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

## Permissions

- `books.create` - Create new layout books
- `books.read_own` - Read your own layout books
- `books.read_any` - Read any user's layout books (admin)
- `books.update_own` - Update your own layout books
- `books.update_any` - Update any layout book (admin)
- `books.delete_own` - Delete your own layout books
- `books.delete_any` - Delete any layout book (admin)

## Endpoints

### Create Layout Book

**POST** `/api/v1/layout-books`

Creates a new layout book from the current workspace configuration.

**Permission**: `books.create`

**Request Body**:
```json
{
  "name": "Python Development Workspace",
  "description": "Optimized for backend development with terminal and file editor",
  "cells": [
    {
      "cellId": "uuid-of-persistent-cell",
      "category": "persistent",
      "type": "file-editor",
      "title": "main.py",
      "position": { "x": 0, "y": 0, "w": 6, "h": 10 },
      "state": { "isMinimized": false, "isMaximized": false }
    },
    {
      "category": "ephemeral",
      "type": "terminal",
      "title": "Backend Terminal",
      "position": { "x": 6, "y": 0, "w": 6, "h": 10 },
      "initialization_data": {
        "shellType": "bash",
        "workingDirectory": "/backend"
      },
      "state": { "isMinimized": false, "isMaximized": false }
    }
  ],
  "grid_config": {
    "cols": 12,
    "rowHeight": 30,
    "margin": [10, 10]
  }
}
```

**Response** `201 Created`:
```json
{
  "id": "layout-book-uuid",
  "assignee_id": "user-uuid",
  "notebook_item_type_id": "layout-book",
  "name": "Python Development Workspace",
  "description": "Optimized for backend development...",
  "type": "VOLATILE",
  "purpose": "Workspace layout template",
  "initial_data": {
    "layout_version": "1.0.0",
    "cells": [...],
    "grid_config": {...},
    "metadata": {
      "cell_count": 2,
      "persistent_count": 1,
      "ephemeral_count": 1,
      "last_applied": null,
      "created_from_layout": true
    }
  },
  "created_at": "2025-12-19T10:30:00Z",
  "updated_at": "2025-12-19T10:30:00Z"
}
```

---

### List Layout Books

**GET** `/api/v1/layout-books`

Lists layout books for the authenticated user with pagination and filtering.

**Permission**: `books.read_own`

**Query Parameters**:
- `skip` (integer, default: 0) - Pagination offset
- `limit` (integer, default: 20, max: 100) - Max results per page
- `name` (string, optional) - Filter by name (partial match, case-insensitive)

**Response** `200 OK`:
```json
{
  "items": [
    {
      "id": "layout-book-uuid-1",
      "name": "Python Development",
      "description": "Backend dev setup",
      "cell_count": 3,
      "persistent_count": 2,
      "ephemeral_count": 1,
      "created_at": "2025-12-19T10:00:00Z",
      "updated_at": "2025-12-19T10:00:00Z"
    },
    {
      "id": "layout-book-uuid-2",
      "name": "Frontend Review",
      "description": "For code review",
      "cell_count": 4,
      "persistent_count": 0,
      "ephemeral_count": 4,
      "created_at": "2025-12-18T15:00:00Z",
      "updated_at": "2025-12-18T15:00:00Z"
    }
  ],
  "total": 2,
  "skip": 0,
  "limit": 20
}
```

---

### Get Layout Book by ID

**GET** `/api/v1/layout-books/{book_id}`

Retrieves a specific layout book with full cell data.

**Permission**: `books.read_own`

**Response** `200 OK`:
```json
{
  "id": "layout-book-uuid",
  "assignee_id": "user-uuid",
  "notebook_item_type_id": "layout-book",
  "name": "Python Development",
  "description": "Backend dev setup",
  "type": "VOLATILE",
  "purpose": "Workspace layout template",
  "initial_data": {
    "layout_version": "1.0.0",
    "cells": [
      {
        "cellId": "cell-uuid",
        "category": "persistent",
        "type": "file-editor",
        "title": "main.py",
        "position": { "x": 0, "y": 0, "w": 6, "h": 10 },
        "state": { "isMinimized": false, "isMaximized": false }
      }
    ],
    "grid_config": {
      "cols": 12,
      "rowHeight": 30,
      "margin": [10, 10]
    },
    "metadata": {
      "cell_count": 1,
      "persistent_count": 1,
      "ephemeral_count": 0,
      "last_applied": null,
      "created_from_layout": true
    }
  },
  "created_at": "2025-12-19T10:00:00Z",
  "updated_at": "2025-12-19T10:00:00Z"
}
```

**Error Responses**:
- `404 Not Found` - Layout book not found
- `403 Forbidden` - Cannot access another user's layout book

---

### Update Layout Book

**PUT** `/api/v1/layout-books/{book_id}`

Updates an existing layout book.

**Permission**: `books.update_own`

**Request Body** (all fields optional):
```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "cells": [...],
  "grid_config": {...}
}
```

**Response** `200 OK`:
```json
{
  "id": "layout-book-uuid",
  "name": "Updated Name",
  "description": "Updated description",
  ...
}
```

**Error Responses**:
- `400 Bad Request` - No fields to update provided
- `404 Not Found` - Layout book not found
- `403 Forbidden` - Cannot update another user's layout book

---

### Delete Layout Book

**DELETE** `/api/v1/layout-books/{book_id}`

Deletes a layout book permanently.

**Permission**: `books.delete_own`

**Response** `204 No Content`

**Error Responses**:
- `404 Not Found` - Layout book not found
- `403 Forbidden` - Cannot delete another user's layout book

---

### Apply Layout Book

**PUT** `/api/v1/layout-books/{book_id}/apply`

Validates a layout book before applying it to the workspace. Checks that all referenced persistent cells still exist.

**Permission**: `books.read_own`

**Response** `200 OK`:
```json
{
  "success": true,
  "book_id": "layout-book-uuid",
  "cells_found": 2,
  "cells_missing": 0,
  "validation_errors": []
}
```

If cells are missing:
```json
{
  "success": false,
  "book_id": "layout-book-uuid",
  "cells_found": 1,
  "cells_missing": 1,
  "validation_errors": [
    "Persistent cell 'main.py' (ID: cell-uuid-123) not found"
  ]
}
```

**Note**: This endpoint only validates server-side. Actual cell restoration happens on the frontend.

---

## Data Models

### CellReference

Represents a cell in a layout book.

**For Persistent Cells**:
```typescript
{
  cellId: string;           // UUID of the persistent cell
  category: "persistent";
  type: string;             // Cell type identifier
  title: string;            // Display title
  position: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  state: {
    isMinimized: boolean;
    isMaximized: boolean;
  };
}
```

**For Ephemeral Cells**:
```typescript
{
  category: "ephemeral";
  type: string;             // Cell type identifier
  title: string;            // Display title
  position: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  initialization_data: {    // Data needed to recreate the cell
    [key: string]: any;
  };
  state: {
    isMinimized: boolean;
    isMaximized: boolean;
  };
}
```

### GridConfig

Grid layout configuration.

```typescript
{
  cols: number;           // Number of columns (default: 12)
  rowHeight: number;      // Height of each row in pixels (default: 30)
  margin: [number, number]; // [horizontal, vertical] margin (default: [10, 10])
}
```

### LayoutBookMetadata

Metadata automatically calculated for each layout book.

```typescript
{
  cell_count: number;           // Total number of cells
  persistent_count: number;     // Number of persistent cells
  ephemeral_count: number;      // Number of ephemeral cells
  last_applied: string | null;  // ISO timestamp of last application
  created_from_layout: boolean; // Always true for user-created books
}
```

---

## Usage Examples

### Save Current Workspace

```javascript
// Frontend: Capture current layout state
const currentLayout = layoutStore.captureCurrentLayout();

// Create layout book
const response = await fetch('/api/v1/layout-books', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'My Workspace',
    description: 'Daily development setup',
    cells: currentLayout.cells,
    grid_config: currentLayout.gridConfig
  })
});

const layoutBook = await response.json();
```

### Load Workspace from Layout Book

```javascript
// 1. Validate layout book
const validateResponse = await fetch(`/api/v1/layout-books/${bookId}/apply`, {
  method: 'PUT',
  headers: { 'Authorization': `Bearer ${token}` }
});

const validation = await validateResponse.json();

if (!validation.success) {
  console.warn('Some cells are missing:', validation.validation_errors);
}

// 2. Get full layout book data
const bookResponse = await fetch(`/api/v1/layout-books/${bookId}`, {
  headers: { 'Authorization': `Bearer ${token}` }
});

const book = await bookResponse.json();

// 3. Restore cells on frontend
await layoutStore.restoreFromLayoutBook(book);
```

---

## Notes

- Layout books are stored as specialized `Book` instances with `notebook_item_type_id = "layout-book"`
- The `cells` array in the Book model is not used for layout books (always empty)
- All cell configuration is stored in `initial_data.cells`
- Grid configuration is captured at save time to ensure consistent layout restoration
- Ephemeral cells include full `initialization_data` to recreate them
- Persistent cells only store a reference (`cellId`) to the actual cell
- The `apply` endpoint validates that persistent cells still exist before restoration
