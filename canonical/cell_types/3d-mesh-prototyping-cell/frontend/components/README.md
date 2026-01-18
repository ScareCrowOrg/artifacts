# 3D Mesh Prototyping Cell - Frontend Components

This directory contains modular Vue components for the 3D Mesh Prototyping Cell frontend interface.

## Components

### GLBModelViewer.vue
**Purpose**: TresJS-based 3D model viewer component  
**Responsibilities**:
- Load GLB models using TresJS `useGLTF` composable
- Handle automatic centering and scaling of models
- Apply wireframe mode to all meshes
- Manage Three.js resource cleanup

**Props**:
- `url: string` - Blob URL of the GLB model to load
- `wireframe: boolean` - Whether to enable wireframe rendering

**Dependencies**: TresJS Core, Three.js

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
- Each component is < 150 lines
- Single responsibility principle
- Props-down, events-up pattern
- Clear separation of concerns

## Usage

Import and use in parent component (ViewTresJS.vue):

```vue
<script setup>
import GLBModelViewer from './components/GLBModelViewer.vue'
import JobStatusIndicator from './components/JobStatusIndicator.vue'
import ViewportControls from './components/ViewportControls.vue'
import MeshMetadataDisplay from './components/MeshMetadataDisplay.vue'
</script>

<template>
  <div>
    <JobStatusIndicator :is-generating="isGenerating" :job-status="status" :job-id="jobId" />
    <ViewportControls @toggle-auto-rotate="handleAutoRotate" ... />
    <TresCanvas>
      <GLBModelViewer :url="modelUrl" :wireframe="wireframeMode" />
    </TresCanvas>
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
- Async GLB loading in GLBModelViewer
- Status color changes in JobStatusIndicator
- Button state changes in ViewportControls
