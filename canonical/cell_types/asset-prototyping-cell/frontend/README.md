# Asset Prototyping Cell – Frontend

## Purpose

Vue 3 frontend for the **Asset Prototyping Cell** — a BaseCell v1.0 composition cell that orchestrates text-to-3D asset generation.

> ⚠️ **DEPRECATED**: This cell is maintained for backward compatibility only.
> New code should use `AssetPrototypingBook` from `artifacts/canonical/book_types/asset-prototyping-book/`.
>
> **Reason**: This cell violates the Single Responsibility Principle by acting as an orchestrator (Book pattern) rather than an atomic executor (Cell pattern). Use `AssetPrototypingBook` for new implementations.

## Content Index

| File | Description |
|------|-------------|
| [`AssetPrototypingCell.ts`](./AssetPrototypingCell.ts) | BaseCell implementation — orchestrates `PngGeneratorCell` and `3DMeshPrototypingCell` to produce 3D assets from text prompts (deprecated) |
| [`View.vue`](./View.vue) | Vue component — prompt input, stage progress visualization, output display |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`tests/`](./tests/) | Unit tests for the cell implementation |

## Related

- [`../`](../) — Asset Prototyping Cell root
- [AssetPrototypingBook](../../../../book_types/asset-prototyping-book/) — The correct replacement using the Book pattern
- [`../../png-generator-cell/`](../../png-generator-cell/) — PNG Generator Cell (Stage 1 dependency)
