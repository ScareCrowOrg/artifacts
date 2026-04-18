# Three.js Scene Generator Cell – Frontend

## Purpose

Vue 3 frontend for the **Three.js Scene Generator Cell** — generates and renders Three.js scenes from natural language descriptions. The generated JavaScript code is executed in a sandboxed canvas element.

## Content Index

| File | Description |
|------|-------------|
| [`View.vue`](./View.vue) | Main component — prompt input, generated code preview, Three.js canvas sandbox, scene controls |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`composables/`](./composables/) | `useThreeJSScene.ts` — scene loading, initialization, execution lifecycle |
| [`translations/`](./translations/) | `en.json`, `pt-BR.json` — i18n strings |

## Related

- [`../`](../) — Three.js Scene Generator Cell root
- [`../../3d-mesh-prototyping-cell/`](../../3d-mesh-prototyping-cell/) — Related 3D scene/mesh cell
