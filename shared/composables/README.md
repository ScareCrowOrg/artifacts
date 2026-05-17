# Shared Composables

Vue composables shared across all ScareVerseLab cell types and the cockpit-vue shell.

## Purpose

This directory provides a single source of truth for reusable Vue composition functions. Cell implementations import from here to avoid duplicating logic and to ensure consistent behavior for core capabilities such as cell lifecycle management, action discovery, permissions, and i18n.

## Index

### Files

| File | Description |
|------|-------------|
| `useActionDiscovery.js` | Discovers available AgenteLab actions from the backend registry |
| `useActionRegistry.js` | Registers and resolves actions at runtime (canonical version) |
| `useActionRegistry-old.js` | Legacy action registry (kept for backward compatibility) |
| `useBookTypeDiscovery.ts` | Discovers available book types from the backend |
| `useBookTypeLoader.ts` | Loads and caches book type definitions |
| `useCellClassLoader.ts` | Dynamically loads cell class modules |
| `useCellDisplay.js` | Controls cell display state (expanded, minimized, fullscreen) |
| `useCellFactory.js` | Factory pattern for creating cell composable instances per UUID |
| `useCellI18n.ts` | i18n helpers scoped to a specific cell instance |
| `useCellInstances.ts` | Manages the lifecycle of active cell instances |
| `useCellManagement.js` | High-level cell CRUD and ordering operations |
| `useCellTypeDiscovery.ts` | Discovers available cell types from the runtime registry |
| `useCellTypeLoader.ts` | Loads and resolves cell type implementations |
| `useCellView.js` | Manages the view state of an individual cell |
| `useCellViewLoader.js` | Asynchronously loads cell view components |
| `useCellViewResolver.js` | Resolves the correct Vue view component for a cell type |
| `useFileBrowser.js` | File-browser state and operations for cells that access the filesystem |
| `useFilenameSuggestion.js` | Generates filename suggestions based on cell content |
| `useFragmentManagement.js` | Manages cell fragments (sub-content within a cell) |
| `useFrontendHealthChecks.ts` | Runs and reports frontend health checks |
| `useI18nHelper.js` | Generic i18n utilities (locale loading, translation fallback) |
| `useImportMap.ts` | Manages ES module import maps for dynamic cell loading |
| `useIssues.js` | Issue tracking integration (create, read, update) |
| `useIssuesDashboard.js` | Data composable for the Issues Dashboard cell |
| `useLogin.js` | Authentication login flow |
| `useModal.js` | Modal dialog lifecycle management |
| `useParentCellContext.ts` | Provides access to parent cell context from nested components |
| `useRequestOrchestrator.js` | Deduplicates and orchestrates concurrent API requests |
| `useServiceConfig.js` | Reads and exposes service configuration from the platform |
| `useSettings.js` | User/workspace settings read and write |
| `useTransmutation.js` | Cell type transmutation (changing a cell's type in place) |
| `useVault.js` | Access to the secret vault for secure credential retrieval |
| `useViewerHandshake.ts` | Handshake protocol between parent shell and embedded cell viewers |
| `useWorkspaceState.js` | Global workspace state (active notebook, selected cells, etc.) |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `actions/` | Action composables organized by domain (AI models, audit, books, cells, config, discovery, GitHub, issues, permissions, proposals, roles, runtime, services, sessions, system, traces, users, utilities) |

## Usage

Import composables via the `@artifacts/shared` path alias:

```ts
import { useBaseCellFeatures } from '@artifacts/shared/composables/useBaseCellFeatures'
import { useCellFactory } from '@artifacts/shared/composables/useCellFactory'
import { usePermissions } from '@artifacts/shared/composables/usePermissions'
```

### Example — wrapping a cell with base features

```ts
const {
  cellData,
  isLoading,
  saveCell,
  deleteCell,
} = useBaseCellFeatures(props.cellId, props.notebookId)
```

## Related Documentation

- [Shared Artifacts Root](../) - Overview of all shared artifacts
- [Shared Components](../components/) - Shared Vue components
- [Shared Stores](../stores/) - Pinia stores used alongside composables
- [Architecture](../../../docs/architecture/) - System architecture documentation
