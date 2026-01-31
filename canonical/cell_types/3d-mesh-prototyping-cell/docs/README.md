---
processed: true
processed_date: 2026-01-31
updated_docs:
  - docs/official/backend/cell-types/3d-mesh-prototyping-cell.md
  - docs/BABYLON_MIGRATION.md
themes:
  - 3d-generation
  - cell-types
  - documentation
  - babylon-js
modules:
  - artifacts
  - backend
  - frontend
code_verified: true
dead_docs_found: false
---
# 3D Mesh Prototyping Cell

## Overview

The **3D Mesh Prototyping Cell** is an advanced interactive cell that enables the generation of real volumetric 3D meshes (with 360º volume) from single input images using AI-powered reconstruction. This cell addresses the ScareVerse project's need for true 3D "Hero Assets" and complex character models that go beyond the 2.5D SVG extrusion approach.

**Technology**: Migrated to **Babylon.js** (2026-01-31) from TresJS for better physics integration, stability, and native Rapier support. See [BABYLON_MIGRATION.md](./BABYLON_MIGRATION.md) for details.

## Features

### Core Capabilities
- **Single Image-to-3D Reconstruction**: Upload a PNG image and generate a complete 3D mesh
- **Real-Time Three.js Preview**: Interactive 3D viewport with orbit controls
- **Optimized GLB Export**: Draco-compressed meshes targeting <5MB file size
- **Viewport Controls**:
  - Auto-rotate toggle
  - Wireframe mode
  - Grid helper display
  - Download GLB functionality
- **Comprehensive Metadata**: Vertices, faces, file size, compression ratio, generation time

### Technical Features
- **GPU-Ready Architecture**: Designed for RTX 4070 local processing
- **Ephemeral Execution**: No database persistence required
- **TypeScript Frontend**: Type-safe Vue 3 Composition API
- **Advanced Logging**: Namespace-based logging system
- **Dark Mode UI**: ScareVerse design system compliant

## Usage

### Basic Workflow

1. **Upload Image**
   - Click "Choose File" and select a PNG/JPG image
   - Preview appears below the upload button

2. **Generate 3D Mesh**
   - Click "Generate 3D Mesh" button
   - Wait for AI reconstruction (target: <20 seconds on RTX 4070)
   - Progress indicator shows generation status

3. **Interact with 3D Model**
   - Use mouse to orbit, zoom, and pan the camera
   - Toggle auto-rotate for continuous rotation
   - Enable wireframe mode to view mesh topology
   - Show/hide grid helper for spatial reference

4. **Download Result**
   - Click "Download GLB" to save the optimized mesh
   - File is Draco-compressed for optimal size (<5MB target)

### Example Use Cases

**Character Prototyping**:
- Upload concept art of a character
- Generate 3D mesh for hero asset
- Download GLB for game engine integration

**Object Creation**:
- Upload photo of a real-world object
- Generate 3D reconstruction
- Use in virtual environments

**Rapid Prototyping**:
- Iterate on asset designs quickly
- Generate multiple variations from different angles
- Select best results for final production

## Technical Architecture

### Frontend (`frontend/View.vue`)

**Technology Stack**:
- Vue 3 with TypeScript
- **Babylon.js** (3D rendering engine)
- SceneLoader (GLB/GLTF loading)
- ArcRotateCamera (orbit controls)

**Key Components**:
- Image upload with FileReader API
- Babylon.js engine initialization (per-cell instance)
- Mesh loading and display
- Viewport control toggles
- Download functionality

**Babylon.js Scene Setup**:
```typescript
- Engine: Per-cell WebGL engine instance
- Scene: Dark background (RGB 0.1, 0.1, 0.1)
- Camera: ArcRotateCamera with orbit controls
- Lighting: HemisphericLight (intensity: 0.8)
- Controls: Native camera controls with zoom limits
- Grid: GridMaterial ground plane (toggleable)
```

### Backend (`backend/scripts/main.py`)

**Execution Interface**:
```python
async def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]
```

**Pipeline Architecture** (Production):
1. **Image Preprocessing**
   - Resize to model input size
   - Normalize pixel values
   - Format conversion

2. **AI Model Inference**
   - Stable Fast 3D (preferred, <1s on RTX 4070)
   - Alternative: InstantMesh
   - Single image → 3D mesh reconstruction

3. **Post-Processing**
   - Mesh decimation (target: 50K faces)
   - UV mapping generation
   - Normal map calculation

4. **GLB Export**
   - GLTF binary format
   - Draco compression (level 7)
   - Size optimization (<5MB target)

**Current Status**: MVP implementation returns mock GLB cube for testing. Real 3D reconstruction requires GPU infrastructure setup.

### Cell Type Definition (`type.json`)

**Key Properties**:
- `inputImage`: Base64-encoded PNG input
- `generatedMesh`: Base64-encoded GLB output
- `meshMetadata`: Statistics (vertices, faces, size, etc.)
- `reconstructionParams`: Generation parameters
- `viewportSettings`: Display configuration

**Default Parameters**:
```json
{
  "targetFaces": 50000,
  "enableDracoCompression": true,
  "compressionLevel": 7,
  "targetFileSizeMB": 5
}
```

## GPU Infrastructure Requirements

### Hardware Prerequisites
- **GPU**: NVIDIA RTX 4070 (or equivalent CUDA-enabled GPU)
- **CUDA**: Version 12.1+ with cuDNN 8+
- **Memory**: 12GB VRAM recommended
- **Environment**: Kind cluster on WSL2/Windows

### Infrastructure Setup (Future)

**Required Configuration**:
1. **Device Mapping**: Expose `/dev/nvidia*` to Kind pods
2. **Container Runtime**: Configure nvidia-container-runtime
3. **CUDA Base Image**: Use `pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime`
4. **Model Caching**: Mount host volume for model weights

**Documentation Reference**:
- Infrastructure: `docs/official/infrastructure/kind-gpu-setup.md` (to be created)
- Cell execution: `docs/issues/implement-ephemeral-execution-flow/`

## API Integration

### Ephemeral Execution Endpoint

**Endpoint**: `POST /api/cells/execute-ephemeral`

**Request**:
```json
{
  "cell_type": "3d-mesh-prototyping-cell",
  "input_data": {
    "inputImage": "data:image/png;base64,iVBORw0KGgo...",
    "reconstructionParams": {
      "targetFaces": 50000,
      "enableDracoCompression": true,
      "compressionLevel": 7,
      "targetFileSizeMB": 5
    }
  }
}
```

**Response**:
```json
{
  "success": true,
  "cell_type": "3d-mesh-prototyping-cell",
  "result": {
    "success": true,
    "generatedMesh": "data:model/gltf-binary;base64,...",
    "meshMetadata": {
      "vertices": 25341,
      "faces": 50000,
      "fileSizeBytes": 456789,
      "compressionRatio": 0.23,
      "generationTimeSeconds": 18.5
    }
  },
  "message": "Ephemeral cell executed successfully"
}
```

## Configuration

### Reconstruction Parameters

**targetFaces** (default: 50000)
- Target face count after decimation
- Higher values = more detail, larger file size
- Recommended range: 10K-100K

**enableDracoCompression** (default: true)
- Enable Draco mesh compression
- Reduces file size by ~70%
- Slight decompression overhead on load

**compressionLevel** (default: 7)
- Draco compression intensity (0-10)
- Higher = smaller file, slower decompression
- Recommended: 5-8 for balanced performance

**targetFileSizeMB** (default: 5)
- Target output file size in megabytes
- Automatic decimation to meet target
- Minimum: 1MB, Maximum: 20MB

### Viewport Settings

**autoRotate** (default: true)
- Automatically rotate mesh on load
- Speed: 2.0 (configurable in code)

**wireframeMode** (default: false)
- Display mesh as wireframe
- Useful for topology inspection

**showGrid** (default: true)
- Display reference grid in scene
- 10x10 unit grid

**cameraPosition** (default: [0, 1, 3])
- Initial camera position [x, y, z]
- Optimized for full mesh visibility

## Testing

### Manual Testing

1. **Start ScareVerse Environment**
   ```bash
   # Backend
   cd backend && poetry run python -m uvicorn app.main:app --reload
   
   # Frontend
   cd cockpit-vue && npm run dev
   ```

2. **Create Cell Instance**
   - Navigate to Cockpit interface
   - Create new "3D Mesh Prototyping Cell"
   - Upload test image
   - Click "Generate 3D Mesh"

3. **Verify Functionality**
   - Check mesh loads in viewport
   - Test all viewport controls
   - Verify download produces valid GLB file
   - Check metadata accuracy

### Automated Tests

**Backend Tests**: `backend/tests/test_3d_mesh_prototyping.py`
```python
# Test execute_cell function
# Test mock mesh generation
# Test error handling
```

**Frontend Tests**: `frontend/tests/View.spec.ts`
```typescript
// Test component rendering
// Test file upload
// Test Three.js initialization
// Test viewport controls
// Test API integration
```

**Coverage Target**: 90% (per RULESET.md §3.1)

## Performance

### Target Metrics
- **Generation Time**: <20 seconds (RTX 4070)
- **File Size**: <5MB (Draco compressed)
- **Viewport FPS**: 60fps (for meshes <100K faces)
- **Initial Load**: <2 seconds (including Draco decompression)

### Current MVP Performance
- **Generation Time**: ~0.1s (mock cube)
- **File Size**: ~1KB (minimal GLB)
- **Viewport FPS**: 60fps (simple geometry)

## Limitations

### Current MVP Limitations
1. **No Real 3D Reconstruction**: Returns mock cube mesh
2. **No GPU Utilization**: Awaits infrastructure setup
3. **No Model Integration**: Stable Fast 3D not yet integrated
4. **Simple Geometry**: Mock cube for testing only

### Production Limitations
1. **Single Image Input**: No multi-view reconstruction
2. **No Animation**: Static meshes only
3. **No Texture Synthesis**: Textures from source image projection
4. **GPU Dependency**: Requires CUDA-capable hardware

## Future Enhancements

### Phase 2: GPU Integration
- [ ] Configure Kind cluster GPU passthrough
- [ ] Integrate Stable Fast 3D model
- [ ] Implement model weight caching
- [ ] Add GPU device detection

### Phase 3: Advanced Features
- [ ] Multi-view reconstruction
- [ ] Texture synthesis and refinement
- [ ] Animation rigging
- [ ] Real-time preview during generation
- [ ] Batch processing
- [ ] Model fine-tuning interface

### Phase 4: Production Optimization
- [ ] Progressive mesh streaming
- [ ] Level-of-detail (LOD) generation
- [ ] Automatic UV unwrapping
- [ ] Normal map baking
- [ ] PBR material generation

## Troubleshooting

### Cell Not Appearing
- **Check Backend Logs**: Ensure cell type was discovered on startup
- **Verify type.json**: Confirm symlink or file exists
- **Restart Backend**: Trigger re-discovery of cell types

### Generation Fails
- **Check API Key**: GPU models may require API authentication
- **Verify Input Image**: Must be valid PNG/JPG format
- **Check Logs**: Review backend logs for detailed errors
- **Simplify Image**: Try smaller, clearer input images

### Mesh Not Loading
- **Check Console**: Look for Three.js or GLTFLoader errors
- **Verify GLB Format**: Ensure valid GLTF binary structure
- **Check Draco**: Verify Draco decoder path is accessible
- **Browser Compatibility**: Requires WebGL 2.0 support

### Performance Issues
- **Reduce Face Count**: Lower `targetFaces` parameter
- **Disable Auto-Rotate**: Can impact lower-end GPUs
- **Close Other Tabs**: Free up GPU memory
- **Update Drivers**: Ensure latest GPU drivers installed

## Compliance

### RULESET.md Adherence
- ✅ **Rule 1.1**: All files <500 lines
- ✅ **Rule 2.1**: README.md present in docs/
- ✅ **Rule 4.5**: Frontend uses TypeScript
- ✅ **Rule 4.7**: Advanced logging system integrated
- ✅ **Rule 3.1**: 90% test coverage target

### TEAM.md Workflow
- ✅ **Ephemeral Pattern**: Uses `/execute-ephemeral` endpoint
- ✅ **Cell Discovery**: Auto-discovered from canonical artifacts
- ✅ **No Persistence**: Category set to "ephemeral"

## References

### Documentation
- [Babylon.js Migration Guide](./BABYLON_MIGRATION.md) ⭐ **NEW**
- [Ephemeral Execution Flow](../../../docs/issues/implement-ephemeral-execution-flow/)
- [RULESET.md](../../../docs/official/RULESET.md)
- [TEAM.md](../../../docs/official/TEAM.md)
- [Cell Type Architecture](../../../docs/official/backend/architecture/)

### External Resources
- [Babylon.js Documentation](https://doc.babylonjs.com/)
- [Babylon.js SceneLoader](https://doc.babylonjs.com/features/featuresDeepDive/Babylon.js_and_WebGL_Advanced_Topics/Loaders/)
- [Babylon.js Physics](https://doc.babylonjs.com/features/featuresDeepDive/Physics/)
- [Stable Fast 3D](https://github.com/Stability-AI/stable-fast-3d) (model reference)

## Support

For issues or questions:
- Create an issue in the ScareVerse repository
- Tag with `cell-type` and `3d-mesh-prototyping` labels
- Include input image, error logs, and environment details

---

**Version**: 2.0.0  
**Created**: 2026-01-16  
**Updated**: 2026-01-31 (Migrated to Babylon.js)  
**Category**: prototyping  
**Status**: MVP - Mock implementation, GPU integration pending  
**Authors**: GitHub Copilot Agent
