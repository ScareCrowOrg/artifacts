# Notebook Cells Admin Cell — Frontend

Vue 3 frontend for the Notebook Cells Admin Cell, providing an administrative interface for browsing, filtering, and managing notebook cell instances.

## Purpose

This package contains the complete frontend implementation of the Notebook Cells Admin Cell: an admin cell that displays all notebook cells across the platform, with filtering, detail views, and management actions.

## Index

### Files

| File | Description |
|------|-------------|
| `NotebookCellsAdminCell.ts` | TypeScript class implementing `BaseCell` for this cell |
| `View.vue` | Root Vue component composing the cell list, filters, and detail panels |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `components/` | UI components (see below) |
| `tests/` | Vitest component and unit tests |
| `translations/` | i18n locale files: `en.json`, `pt-BR.json` |

## Components

| Component | Description |
|-----------|-------------|
| `NotebookCellList.vue` | Paginated list of notebook cell instances with type badges and status indicators |
| `NotebookCellDetails.vue` | Expanded detail panel showing cell metadata, data payload, and history |
| `NotebookCellFilters.vue` | Filter controls for type, status, notebook, and date range |
| `JsonEditor.vue` | Inline JSON editor for modifying cell `initial_data` or `refs` |
| `JsonViewer.vue` | Read-only JSON viewer for displaying cell data payloads |

## Usage

The cell is an **admin cell** rendered inside the cockpit-vue shell. It communicates with `notebookCellsService.js` from `@artifacts/shared/services/` to fetch and update cell records.

## Related Documentation

- [Notebook Cells Admin Cell Root](../) - Full cell overview and `type.json` specification
- [Shared Services](../../../../shared/services/) - `notebookCellsService.js`
- [Shared i18n Locales](../../../../shared/i18n/locales/) - Base translations extended here
