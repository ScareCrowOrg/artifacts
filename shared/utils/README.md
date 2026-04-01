# Shared Utilities

General-purpose utility modules shared across all ScareVerseLab cell types and the cockpit-vue shell.

## Purpose

This directory provides low-level utilities that are not specific to any single cell or service. Utilities here handle cross-cutting concerns such as structured logging, cell registry management, dynamic form generation, data diffing, and browser storage abstraction.

## Index

### Files

| File | Description |
|------|-------------|
| `CellRegistry.js` | Factory pattern registry for per-UUID composable instances; eliminates singleton state pollution and race conditions |
| `DynamicFormGenerator.ts` | Converts a JSON Schema (`properties_schema`) from a cell type definition into Vue form field descriptors |
| `cellTypeLoaderUtil.ts` | Utility functions for loading and resolving cell type modules from the import map |
| `diffUtils.js` | Lightweight diffing utilities for comparing cell data objects (used for optimistic updates and change detection) |
| `indexeddb-wrapper.js` | Promise-based wrapper around the browser IndexedDB API (used for offline layout persistence) |
| `logger.js` | Advanced structured logging system for Vue.js with namespace/key-based control, log levels, and optional remote transport |
| `logger.d.ts` | TypeScript declaration file for `logger.js` — enables typed imports in `.ts` files |

## Key Utilities

### `logger.js`

The standard logging utility for all frontend code. Supports:

- Namespace-based log control (enable/disable per module)
- Log levels: `debug`, `info`, `warn`, `error`
- Structured metadata attachment
- Optional remote log transport

```js
import { createLogger } from '@artifacts/shared/utils/logger'

const log = createLogger('my-cell')
log.info('Cell initialized', { cellId, notebookId })
log.error('Execution failed', { error })
```

### `CellRegistry.js`

Manages per-UUID composable instances to prevent state leakage between cells:

```js
import { CellRegistry } from '@artifacts/shared/utils/CellRegistry'

const registry = new CellRegistry()
const instance = registry.getOrCreate(cellId, () => useMyCellComposable())
```

### `DynamicFormGenerator.ts`

Converts cell type JSON schemas to form fields for the cell configuration UI:

```ts
import { generateFormFields } from '@artifacts/shared/utils/DynamicFormGenerator'

const fields = generateFormFields(cellType.properties_schema)
// → [{ name: 'model_path', type: 'text', label: 'Model Path', required: true }, ...]
```

## Related Documentation

- [Shared Artifacts Root](../) - Overview of all shared artifacts
- [Shared Composables](../composables/) - `useCellFactory` uses `CellRegistry`
- [Shared Types](../types/) - Type definitions used by `DynamicFormGenerator`
