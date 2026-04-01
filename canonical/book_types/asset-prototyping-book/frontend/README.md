# Asset Prototyping Book — Frontend

TypeScript implementation of the Asset Prototyping Book, a DAG-based orchestrator that creates complete 3D assets from text prompts by composing the PNG Generator and 3D Mesh Prototyping cells.

## Purpose

This package contains the `AssetPrototypingBook` class, which implements the `BaseBook` interface to orchestrate a two-cell pipeline: PNG generation from a text prompt followed by 3D mesh generation from the resulting image. It demonstrates the **Book Pattern** for separating orchestration from atomic cell execution.

## Index

### Files

| File | Description |
|------|-------------|
| `AssetPrototypingBook.ts` | `BaseBook` implementation that defines the DAG for the asset prototyping pipeline |

## Architecture

```
Text Prompt
     ↓
[PNG Generator Cell]   ← Node 1 (generates reference image)
     ↓
[3D Mesh Prototyping Cell]  ← Node 2 (generates 3D mesh from image)
     ↓
Complete 3D Asset (GLB/GLTF)
```

The `AssetPrototypingBook`:
- Defines the DAG with two nodes and a directed edge (PNG → 3D Mesh)
- Handles state transfer (passes PNG output URL as input to 3D Mesh cell)
- Implements `getDAG()` and `describe()` from `BaseBookImpl`

## Usage

```ts
import { AssetPrototypingBook } from '@artifacts/book_types/asset-prototyping-book/frontend/AssetPrototypingBook'

const book = new AssetPrototypingBook()
const result = await book.execute({ prompt: 'a futuristic spaceship' })
// → { modelUrl: 'https://...', metadata: { format: 'glb', ... } }
```

## Related Documentation

- [Asset Prototyping Book Root](../) - Full book type overview and `type.json`
- [Shared Types / BaseBook](../../../shared/types/) - `BaseBook` and `BaseBookImpl` interfaces
- [PNG Generator Cell](../../cell_types/png-generator-cell/) - First node in the pipeline
- [3D Mesh Prototyping Cell](../../cell_types/3d-mesh-prototyping-cell/) - Second node in the pipeline
