---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/backend/security/cell-types-security.md
themes:
  - cells
  - frontend
  - fragments
modules:
  - frontend
code_verified: true
dead_docs_found: false
---
# Fragment Editor Cell

## Overview

The **Fragment Editor Cell** provides fragment editing capabilities within the Dynamic Workspace. It allows users to create and edit fragments (markdown content) for cells in the ScareVerse ecosystem.

## Type

- **ID**: `fragment-editor-cell`
- **Name**: Fragment Editor
- **Category**: content
- **Version**: 1.0.0

## Purpose

This cell migrates the functionality from the legacy `FragmentEditorModal.vue` component into the canonical cell architecture, following the BaseCell v1.0 pattern.

## Features

- ✅ Create new fragments with markdown content
- ✅ Edit existing fragments
- ✅ Load fragment data for cells
- ✅ Markdown editor integration
- ✅ i18n support for internationalization
- ✅ Theme compliance (dark mode support)
- ✅ Accessibility features (ARIA labels, keyboard navigation)

## Architecture

### Frontend Structure

```
fragment-editor-cell/
├── frontend/
│   ├── FragmentEditorCell.ts   # BaseCell implementation
│   ├── View.vue                  # Main Vue component
│   ├── composables/
│   │   └── useFragmentEditor.ts  # Fragment editing logic
│   └── tests/
│       ├── FragmentEditorCell.test.ts
│       └── View.test.ts
├── docs/
│   └── README.md                 # This file
└── type.json                     # Symlink to canonical type definition
```

### BaseCell Interface

The cell implements the mandatory BaseCell interface methods:

- **execute(input)**: Saves/loads fragment data via API
- **describe()**: Returns cell metadata and capabilities
- **validate(input)**: Validates input parameters

## Usage

### Creating a New Fragment

```typescript
const cell = new FragmentEditorCell()

const result = await cell.execute({
  action: 'create',
  cellId: 'cell-123',
  content: '# My Fragment\n\nSome content...'
})
```

### Editing an Existing Fragment

```typescript
const result = await cell.execute({
  action: 'edit',
  cellId: 'cell-123',
  fragmentId: 'fragment-456',
  content: '# Updated Fragment\n\nUpdated content...'
})
```

### Loading a Fragment

```typescript
const result = await cell.execute({
  action: 'load',
  fragmentId: 'fragment-456'
})
```

## Input Schema

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | Yes | Action to perform: 'create', 'edit', or 'load' |
| `cellId` | string | Conditional | Required for create/edit actions |
| `fragmentId` | string | Conditional | Required for edit/load actions |
| `content` | string | Conditional | Required for create/edit actions |

## Output Schema

```typescript
{
  success: boolean        // Whether the operation succeeded
  output: {
    fragmentId?: string   // ID of the created/updated fragment
    content?: string      // Fragment content (for load action)
    cellId?: string       // Cell ID
  }
  execution_time: number  // Execution time in milliseconds
  error?: string          // Error message if operation failed
}
```

## API Integration

The cell uses the existing `/api/cells/{cell_id}/update` endpoint to save fragments. No new backend endpoints are required.

## Tests

- **Unit Tests**: `frontend/tests/FragmentEditorCell.test.ts`
- **Component Tests**: `frontend/tests/View.test.ts`
- **Coverage Target**: 90%+

## Dependencies

- Vue 3
- Vue I18n (for internationalization)
- MarkdownEditor component
- BaseCell interface from `@/types/BaseCell`

## Migration Notes

This cell replaces the legacy `FragmentEditorModal.vue` component, which was:
- Tightly coupled to App.vue
- Triggered by store-based events
- Not following the BaseCell pattern

The new cell-based implementation:
- Follows BaseCell v1.0 architecture (Rule 4.8)
- Uses TypeScript (Rule 4.5)
- Located in canonical cell directory
- Can be executed headlessly
- Properly validated and documented

## Related Documentation

- [BaseCell Interface](../../../cockpit-vue/src/types/BaseCell.ts)
- [ADDING_NEW_CELL_TYPE.md](../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [RULESET.md](../../../docs/official/RULESET.md)

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-22 | Initial implementation |
