# 3D Mesh Prototyping Cell — Frontend

Vue 3 frontend for the 3D Mesh Prototyping Cell, providing image-to-3D generation and interactive 3D model preview within the ScareVerse Cockpit.

## Purpose

This package contains the complete frontend implementation for the 3D Mesh Prototyping Cell: the main view, upload/generation UI components, job polling composable, and tests.

## Index

### Files

| File | Description |
|------|-------------|
| `MeshPrototypingCell.ts` | TypeScript class implementing `BaseCell` for this cell — handles initialization, execution dispatch, and lifecycle |
| `View.vue` | Root Vue component that composes the upload form, job status indicator, and 3D model viewer |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `components/` | UI components for the cell (see below) |
| `composables/` | `useJobPolling.ts` — polls the backend for async job status updates |
| `tests/` | Vitest tests: `MeshPrototypingCell.test.ts` and `README.md` explaining the test strategy |

## Components

| Component | Description |
|-----------|-------------|
| `GLBFileUploader.vue` | Drag-and-drop file uploader for `.glb`/`.gltf` model files |
| `GenerationModeSwitcher.vue` | Switcher UI for selecting generation mode (`cloud-api`, `local-gpu`, `manual-upload`) |
| `JobStatusIndicator.vue` | Real-time job status badge (queued, processing, complete, failed) |
| `MeshMetadataDisplay.vue` | Displays mesh metadata (polygon count, format, file size) |
| `ViewportControls.vue` | Camera/viewport control overlay for the 3D viewer (zoom, reset, fullscreen) |

## Key Composable

### `useJobPolling.ts`

Polls the backend job status endpoint at configurable intervals until the job reaches a terminal state (`complete` or `failed`). Emits progress events that `View.vue` uses to update the UI in real time.

## Usage

The frontend is loaded dynamically by the cockpit-vue shell when a 3D Mesh Prototyping Cell is activated. The 3D model is rendered using `BabylonModelViewer` from `@artifacts/shared/components/viewers/`.

```bash
# Run tests
npx vitest run artifacts/canonical/cell_types/3d-mesh-prototyping-cell/frontend/tests/
```

## Related Documentation

- [3D Mesh Prototyping Cell Root](../) - Full cell overview including backend
- [3D Mesh Prototyping Backend](../backend/) - Python execution backend
- [Shared Viewers](../../../../shared/components/viewers/) - `BabylonModelViewer` component
- [Shared Composables](../../../../shared/composables/) - Platform-wide composables
