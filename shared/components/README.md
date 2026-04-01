# Shared Components

Reusable Vue components shared across all ScareVerseLab cell types and frontend modules.

## Purpose

This directory contains generic UI components and specialized viewers that are used by multiple cell implementations. Keeping these components here avoids duplication and ensures consistent behavior across the platform.

## Index

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `viewers/` | Specialized 3D/media viewer components (e.g., `BabylonModelViewer.vue`) |
| `actions/` | Action composables organized by domain (AI models, books, cells, config, discovery, etc.) |

## Overview

Shared components follow the same conventions as regular Vue components in the cockpit-vue shell:

- **Props**: Explicitly typed using TypeScript or JSDoc
- **Emits**: Declared with `defineEmits`
- **Scoped styles**: Use `<style scoped>` to avoid global leakage

## Usage

Import shared components using the `@artifacts/shared` path alias (configured in each cell's `vite.config.js`):

```js
import BabylonModelViewer from '@artifacts/shared/components/viewers/BabylonModelViewer.vue'
```

Or via relative import from within `artifacts/`:

```js
import BabylonModelViewer from '../components/viewers/BabylonModelViewer.vue'
```

## Related Documentation

- [Shared Artifacts Root](../) - Overview of all shared artifacts
- [Composables](../composables/) - Shared Vue composables
- [Services](../services/) - Shared service modules
- [ScareVerse Architecture](../../../docs/architecture/) - System architecture docs
