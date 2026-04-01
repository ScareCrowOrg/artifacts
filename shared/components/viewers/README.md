# Shared Component Viewers

Specialized 3D and media viewer Vue components shared across ScareVerseLab cell types.

## Purpose

This directory contains viewer components that render complex content such as 3D models inside cell UIs. These viewers are shared rather than duplicated so that rendering improvements and bug fixes propagate to all consumers automatically.

## Index

### Files

| File | Description |
|------|-------------|
| `BabylonModelViewer.vue` | Vue component that renders 3D models using Babylon.js inside a canvas element |

## Overview

### BabylonModelViewer

Wraps the Babylon.js engine to load and display `.glb`/`.gltf` 3D models. It is used by the **3D Mesh Prototyping Cell** and any other cell that needs interactive 3D model preview.

Key capabilities:

- Loads models from URLs or blob references
- Provides orbit camera controls (pan, zoom, rotate)
- Emits events when the model finishes loading or encounters an error
- Supports transparency/background-color customization via props

## Usage

```vue
<template>
  <BabylonModelViewer
    :model-url="cell.data.modelUrl"
    background-color="#1a1a2e"
    @loaded="onModelLoaded"
    @error="onModelError"
  />
</template>

<script setup>
import BabylonModelViewer from '@artifacts/shared/components/viewers/BabylonModelViewer.vue'
</script>
```

## Related Documentation

- [Shared Components](../) - Parent directory overview
- [Shared Artifacts Root](../../) - Overview of all shared artifacts
- [3D Mesh Prototyping Cell](../../../canonical/cell_types/3d-mesh-prototyping-cell/) - Primary consumer
