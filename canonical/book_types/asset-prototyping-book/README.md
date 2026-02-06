# Asset Prototyping Book

DAG-based orchestrator for creating complete 3D assets from text prompts.

## Overview

The Asset Prototyping Book demonstrates the BaseBook pattern by orchestrating PNG generation and 3D mesh prototyping to create textured 3D assets.

**Refactoring Note**: This book replaces the orchestration logic previously embedded in `AssetPrototypingCell` (PR 2309), properly separating orchestration concerns from atomic cell execution.

## Workflow

```
Text Prompt
    ↓
[PngGeneratorCell] → Texture PNG
    ↓
[MeshPrototypingCell] → 3D Mesh (GLB)
    ↓
Combined Asset
```

## Usage

### Basic Example

```typescript
import { 
  AssetPrototypingBook, 
  registerAssetPrototypingCells 
} from '@/artifacts/canonical/book_types/asset-prototyping-book/frontend/AssetPrototypingBook'

// Register required cell types (once per application)
registerAssetPrototypingCells()

// Create book instance
const book = new AssetPrototypingBook()

// Setup
await book.setup({
  headless_mode: true,
  has_gpu: false,
  gpu_vram_mb: 0,
  cpu_cores: 4,
  timeout_seconds: 300
})

// Execute workflow
const result = await book.execute({
  prompt: 'a fantasy sword with ornate handle',
  asset3dMode: true,
  generationMode: 'cloud-api'
})

// Access results
console.log('Texture:', result.output.texturePng)
console.log('Mesh URL:', result.output.meshGlbUrl)
console.log('Timing:', result.output.metadata)

// Cleanup
await book.teardown()
```

### Advanced Options

```typescript
const result = await book.execute({
  // Required
  prompt: 'cyberpunk helmet with neon accents',
  
  // Optional
  negativePrompt: 'blurry, low quality, distorted',
  asset3dMode: true,
  generationMode: 'cloud-api', // or 'local-gpu' or 'manual-upload'
  reconstructionParams: {
    targetFaces: 10000,
    enableDracoCompression: true,
    compressionLevel: 7
  }
})
```

## Input Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `prompt` | string | Yes | - | Text description of asset to generate |
| `negativePrompt` | string | No | - | Features to exclude from generation |
| `asset3dMode` | boolean | No | true | Enable 3D asset optimization |
| `generationMode` | string | No | 'cloud-api' | Mesh generation mode |
| `reconstructionParams` | object | No | - | Mesh reconstruction settings |

### Reconstruction Parameters

| Field | Type | Description |
|-------|------|-------------|
| `targetFaces` | number | Target face count (100-100000) |
| `enableDracoCompression` | boolean | Enable Draco compression |
| `compressionLevel` | number | Compression level (0-10) |

## Output Schema

```typescript
{
  texturePng: string           // Base64-encoded texture PNG
  meshGlbUrl?: string          // URL to download GLB file
  jobId?: string               // Job ID (for local-gpu mode)
  message: string              // Status message
  metadata: {
    textureGenTime: number     // PNG generation time (ms)
    meshGenTime: number        // Mesh generation time (ms)
    totalTime: number          // Total execution time (ms)
    prompt: string             // Original prompt
  }
}
```

## DAG Structure

### Nodes

1. **generate_texture** (PngGeneratorCell)
   - Input: prompt, negativePrompt, asset3dMode
   - Output: generatedPng (base64)

2. **generate_mesh** (MeshPrototypingCell)
   - Input: inputImage (from generate_texture), reconstructionParams, generationMode
   - Output: glb_url, job_id

### Dependencies

- generate_mesh depends on generate_texture
- Execution order: texture → mesh

## Performance

- **Estimated Duration**: ~30 seconds
  - PNG Generation: ~10 seconds
  - Mesh Generation: ~20 seconds
- **Required Resources**:
  - Backend API
  - Stable Diffusion service
  - 3D Generation API

## Composed Cells

This book uses the following cells:

1. **PngGeneratorCell** (`artifacts/canonical/cell_types/png-generator-cell/`)
   - Generates texture images from text prompts
   - Supports 3D asset mode for better texture quality

2. **MeshPrototypingCell** (`artifacts/canonical/cell_types/3d-mesh-prototyping-cell/`)
   - Creates 3D meshes from input images
   - Supports multiple generation modes

## Testing

```bash
# Run book tests
npm run test -- artifacts/canonical/book_types/asset-prototyping-book/frontend/tests
```

## Comparison with AssetPrototypingCell

### Old Approach (Cell-based Orchestration)

**Problems**:
- ❌ Cell contains other cells (wrong abstraction)
- ❌ Manual state transfer
- ❌ Duplicated orchestration code
- ❌ Hard to test
- ❌ Poor reusability

```typescript
// OLD: AssetPrototypingCell
class AssetPrototypingCell implements BaseCell {
  private pngCell = new PngGeneratorCell()
  private meshCell = new MeshPrototypingCell()
  
  async execute(input) {
    const pngResult = await this.pngCell.execute(...)
    const meshResult = await this.meshCell.execute({
      inputImage: pngResult.output.generatedPng  // Manual transfer
    })
    return { /* aggregate manually */ }
  }
}
```

### New Approach (Book-based Orchestration)

**Benefits**:
- ✅ Declarative DAG definition
- ✅ Automatic state transfer
- ✅ Reusable cells
- ✅ Testable orchestration
- ✅ No code duplication

```typescript
// NEW: AssetPrototypingBook
class AssetPrototypingBook extends AbstractBaseBook {
  getDAG() {
    return {
      nodes: [
        { id: 'generate_texture', cellType: 'png-generator-cell', ... },
        { id: 'generate_mesh', cellType: '3d-mesh-prototyping-cell', ... }
      ],
      edges: [{ from: 'generate_texture', to: 'generate_mesh' }]
    }
  }
}
```

## Migration from AssetPrototypingCell

The `AssetPrototypingCell` is maintained for backward compatibility but is considered deprecated. New code should use `AssetPrototypingBook`.

### Migration Steps

1. Replace `AssetPrototypingCell` import with `AssetPrototypingBook`
2. Call `registerAssetPrototypingCells()` once at startup
3. Use `book.execute()` instead of `cell.execute()`
4. Update tests to use book pattern

## Related

- [BaseBook Framework](../../README.md) - Book pattern overview
- [PngGeneratorCell](../../../cell_types/png-generator-cell/) - Texture generation
- [MeshPrototypingCell](../../../cell_types/3d-mesh-prototyping-cell/) - 3D mesh creation
- [BaseCell v1.0](../../../../docs/issues/base-cell-v1-implementation/) - Cell framework docs

## Files

- `frontend/AssetPrototypingBook.ts` - Book implementation
- `frontend/tests/` - Test suite
- `README.md` - This file
