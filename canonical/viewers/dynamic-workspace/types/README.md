# DynamicWorkspace Types

Shared TypeScript type definitions for the DynamicWorkspace v2 viewer, used across composables, components, and the root `App.vue`.

## Purpose

This directory centralizes all TypeScript interfaces and types for the DynamicWorkspace viewer:
- **Cell type definitions**: Describes cell types loaded from HybridDatabase canonical JSONs
- **Grid cell model**: Describes an instantiated cell within the grid (state, position, view)
- **Position types**: Grid coordinate and size definitions
- **View spec**: The render contract between a cell instance and the grid

## Directory Structure

```
types/
└── index.ts   - All shared type definitions (CellTypeDefinition, GridCell, GridPosition, ViewSpec, etc.)
```

## How to Use

```typescript
import type {
  CellTypeDefinition,
  GridCell,
  GridPosition,
  ViewSpec
} from '../types'

// CellTypeDefinition: loaded from HybridDatabase
const cellType: CellTypeDefinition = {
  name: 'calculator-cell',
  id: 'uuid-...',
  displayName: 'Calculator'
}

// GridCell: instantiated cell in the workspace grid
const gridCell: GridCell = {
  id: 'cell-1',
  typeName: 'calculator-cell',
  state: 'ready',
  position: { x: 0, y: 0, w: 4, h: 3 }
}
```

## Content Index

| File | Description |
|---|---|
| `index.ts` | All shared TypeScript types: `CellTypeDefinition`, `GridCell`, `GridPosition`, `ViewSpec`, and more |
