---
processed: true
processed_date: 2026-02-14
themes:
  - cell-types
  - asset-generation
  - prototyping
modules:
  - asset-prototyping-cell
code_verified: false
---

# 🎨 Asset Prototyping Cell

## Overview

The **AssetPrototypingCell** is a full-stack cell designed for rapid prototyping of assets, integrating 3D mesh generation, texturing, and basic animation capabilities. It serves as a foundational cell for creating visual assets within the ScareVerse Cockpit.

## Purpose

Enable users to:
- Generate basic 3D assets by combining primitive shapes and applying procedural textures.
- Define simple animation sequences for assets.
- Export assets in formats suitable for integration into larger scenes or projects.
- Serve as a template for more complex asset generation cells.

## Key Features

- **Asset Composition**: Combine primitive shapes (e.g., from 3DMeshPrototypingCell) with textures.
- **Procedural Texturing**: Apply basic procedural textures or color schemes.
- **Simple Animation**: Define keyframe animations for transformations.
- **Export Capabilities**: Export combined assets and animations.
- **Full-Stack Architecture**: Utilizes both frontend and backend components.
- **Canonical Cell**: Adheres to BaseCell v1.0 architecture.

## Directory Structure

```
asset-prototyping-cell/
├── README.md                           # This file
├── type.json                           # 🔗 Symlink to ../../notebook_item_types/asset-prototyping-cell.json
├── frontend/                           # Frontend implementation
│   ├── README.md                       # Frontend components documentation
│   ├── {CellName}.ts                   # BaseCell/RenderableCell implementation
│   ├── View.vue                        # Main Vue component for UI
│   ├── types.ts                        # TypeScript type definitions
│   └── components/                     # (Optional) Vue components
└── backend/                            # Backend implementation
    ├── README.md                       # Backend implementation documentation
    ├── scripts/                        # Contains backend scripts, main logic may reside here.
    │   └── main.py                     # Python class extending BaseCell ABC (if present, check scripts dir)
    └── tests/
        ├── README.md                   # Backend tests documentation
        └── test_asset_prototyping_cell_basecell.py # Backend unit tests
```

## Technical Details

- **TypeScript**: Frontend implementation is in TypeScript (RULESET.md Rule 4.5).
- **Python**: Backend logic is implemented in Python.
- **File Size**: All files adhere to the 500-line limit (RULESET.md Rule 1.1).
- **Canonical Cell**: Follows BaseCell v1.0 structure (RULESET.md Rule 4.8).

## Usage

1. **Select Base Mesh**: Choose a primitive shape or upload a base mesh.
2. **Apply Textures**: Select or generate procedural textures.
3. **Define Animations**: Set up basic keyframe animations.
4. **Export Asset**: Save the complete asset in a desired format.

## Testing Strategy

- **Frontend**: Unit and component tests for UI, state management, and `RenderableCell` methods.
- **Backend**: Unit tests for `BaseCell` implementation, asset generation, texturing, and animation logic.
- **Integration**: Test interactions between frontend, backend, and potentially other asset-related cells.
- **Coverage**: Maintain 90%+ test coverage (RULESET.md Rule 3.1).

## Related Components

- **3DMeshPrototypingCell**: Provides base mesh generation.
- **PlannerCell**: May define requirements for specific asset types.
- **CoderCell**: Could be used to generate variations or more complex asset cells.

---

**Version**: 1.0.0  
**Category**: asset-generation  
**Status**: Development - Frontend implementation exists. Backend implementation pending or minimal (check scripts dir).
