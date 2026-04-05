---
processed: true
processed_date: "2026-01-31"
updated: true
generated_docs:
  - "docs/official/frontend/architecture/cell-type-examples-patterns.md"
themes:
  - "cell-architecture"
  - "component-design"
  - "3d-rendering"
  - "babylon-js"
modules:
  - "frontend"
  - "artifacts"
code_verified: true
dead_docs_found: false
---

# 3D Mesh Prototyping Cell - Frontend Components

This directory contains modular Vue components for the 3D Mesh Prototyping Cell frontend interface.

**Migration Note**: Migrated from TresJS to Babylon.js on 2026-01-31. See [BABYLON_MIGRATION.md](../../docs/BABYLON_MIGRATION.md) for details.

## Components

### BabylonModelViewer.vue
**Purpose**: Babylon.js-based 3D model viewer component  
**Responsibilities**:
- Initialize per-cell Babylon.js Engine and Scene
- Load GLB models using Babylon.js SceneLoader
- Handle automatic centering and scaling of models
- Apply wireframe mode to all meshes
- Manage camera controls (ArcRotateCamera with orbit)
- Create and display ground grid (GridMaterial)
- Proper resource cleanup and disposal

**Props**:
- `url: string` - Blob URL of the GLB model to load
- `wireframe: boolean` - Whether to enable wireframe rendering
- `autoRotate: boolean` - Enable camera auto-rotation
- `showGrid: boolean` - Display ground grid

**Dependencies**: @babylonjs/core, @babylonjs/loaders, @babylonjs/materials

**Architecture**: Per-cell Engine pattern - each component creates its own Babylon.js Engine instance for input isolation and clean resource management.

### JobStatusIndicator.vue
**Purpose**: Real-time job status display component  
**Responsibilities**:
- Show current job processing status
- Display job ID for tracking
- Provide visual feedback with color-coded status
- Animate processing indicator

**Props**:
- `isGenerating: boolean` - Whether a job is currently running
- `jobStatus: string` - Current job status (idle/queued/processing/completed/failed)
- `jobId: string | null` - Unique job identifier

### ViewportControls.vue
**Purpose**: 3D viewport control buttons  
**Responsibilities**:
- Toggle auto-rotate mode
- Toggle wireframe rendering
- Toggle grid helper visibility
- Trigger GLB download

**Props**:
- `autoRotate: boolean` - Current auto-rotate state
- `wireframeMode: boolean` - Current wireframe state
- `showGrid: boolean` - Current grid visibility state
- `hasMesh: boolean` - Whether a mesh is loaded

**Events**:
- `@toggle-auto-rotate` - Emitted when auto-rotate is toggled
- `@toggle-wireframe` - Emitted when wireframe is toggled
- `@toggle-grid` - Emitted when grid is toggled
- `@download-mesh` - Emitted when download is requested

### MeshMetadataDisplay.vue
**Purpose**: Display mesh statistics and processing metrics  
**Responsibilities**:
- Show mesh geometry information (vertices, faces)
- Display file size and compression status
- Show processing times (SF3D, Blender, total)
- Display any notes or warnings

**Props**:
- `metadata: Record<string, any> | null` - Mesh metadata object

## Architecture

These components follow the modular design principles from RULESET.md:
- Each component is < 200 lines (BabylonModelViewer: ~250 lines due to engine setup)
- Single responsibility principle
- Props-down, events-up pattern
- Clear separation of concerns
- Proper resource lifecycle management

**Babylon.js Integration**:
- Per-cell Engine architecture (not global shared engine)
- Each viewer creates independent Engine + Scene + Camera
- Natural input isolation via camera.attachControl(localCanvas)
- Clean disposal on unmount (engine.dispose())

## Usage

Import and use in parent component (View.vue):

```vue
<script setup>
import BabylonModelViewer from './components/BabylonModelViewer.vue'
import JobStatusIndicator from './components/JobStatusIndicator.vue'
import ViewportControls from './components/ViewportControls.vue'
import MeshMetadataDisplay from './components/MeshMetadataDisplay.vue'
</script>

<template>
  <div>
    <JobStatusIndicator :is-generating="isGenerating" :job-status="status" :job-id="jobId" />
    <ViewportControls @toggle-auto-rotate="handleAutoRotate" ... />
    <div class="viewport-container">
      <BabylonModelViewer 
        :url="modelUrl" 
        :wireframe="wireframeMode"
        :auto-rotate="autoRotate"
        :show-grid="showGrid"
      />
    </div>
    <MeshMetadataDisplay :metadata="meshMetadata" />
  </div>
</template>
```

## Testing

Unit tests for these components should be added to:
`/home/runner/_work/ScareVerseLab/ScareVerseLab/artifacts/canonical/cell_types/3d-mesh-prototyping-cell/frontend/tests/`

Test coverage should validate:
- Component rendering with various props
- Event emission
- Async GLB loading in BabylonModelViewer
- Engine initialization and disposal
- Camera controls and auto-rotation
- Grid material creation
- Status color changes in JobStatusIndicator
- Button state changes in ViewportControls

## Archived Components

### GLBModelViewer.vue.tresjs.archived
Former TresJS-based viewer, archived during Babylon.js migration (2026-01-31).
Kept for reference but should not be used in new code.
