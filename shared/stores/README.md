# Shared Stores

Pinia stores shared across all ScareVerseLab cell types and the cockpit-vue shell.

## Purpose

This directory contains Pinia stores that manage global and cross-cell state. Individual cells access these stores via composables or direct `useXxxStore()` calls. Centralizing state here prevents duplicated reactive state and race conditions caused by multiple singleton stores.

## Index

### Files

| File | Description |
|------|-------------|
| `actions.js` | Store for queued AgenteLab actions (pending, in-progress, completed) |
| `cellInstancesStore.ts` | Manages per-UUID composable instances; implements the factory pattern for cell state isolation |
| `cells.js` | Global list of active cells, their metadata, and selection state |
| `chat.ts` | Chat-IA conversation state: messages, session ID, streaming status |
| `fileBrowser.js` | File-browser tree state (expanded nodes, selected file, loading indicators) |
| `globalEvents.js` | Legacy global event bus (JS version; prefer `globalEvents.ts`) |
| `globalEvents.ts` | Typed global event bus for cross-component communication |
| `issues.js` | GitHub issues state: list, filters, selected issue, pagination |
| `layout.js` | Workspace layout state: panel sizes, collapsed panels, grid configuration |
| `modals.js` | Modal stack management: open/close modals with payload and result callbacks |
| `notebookCells.js` | Ordered list of notebook cells (display order, visibility, grouping) |
| `permissions.js` | Current user's RBAC permissions and role assignments |
| `services.js` | Service registry state: available backend services and their health status |
| `settings.js` | User and workspace settings (theme, locale, feature flags) |
| `ui.js` | Legacy UI state (JS version; prefer `ui.ts`) |
| `ui.ts` | Typed UI state: loading spinners, toast notifications, sidebar visibility |
| `useNotebookStore.js` | Composable-style wrapper around the notebook Pinia store |
| `workspace.js` | Legacy workspace state (JS version; prefer `workspaceStore.ts`) |
| `workspaceStore.ts` | Typed workspace state: active notebook, active book, open panels |

## Usage

```ts
import { useCellsStore } from '@artifacts/shared/stores/cells'
import { useWorkspaceStore } from '@artifacts/shared/stores/workspaceStore'
import { usePermissionsStore } from '@artifacts/shared/stores/permissions'

const cellsStore = useCellsStore()
const workspaceStore = useWorkspaceStore()
const permissionsStore = usePermissionsStore()

// Access active notebook
const notebookId = workspaceStore.activeNotebookId

// Check permission
if (permissionsStore.can('cells:delete')) {
  await cellsStore.deleteCell(cellId)
}
```

## Notes

- Files with both `.js` and `.ts` variants: the `.ts` version is the current canonical implementation. The `.js` version is kept for backward compatibility during the TypeScript migration.
- Stores use the Pinia **Options API** style for legacy files and the **Setup Store** style for newer `.ts` files.

## Related Documentation

- [Shared Artifacts Root](../) - Overview of all shared artifacts
- [Shared Composables](../composables/) - Composables that wrap these stores
- [Shared Services](../services/) - Service modules that populate store state
