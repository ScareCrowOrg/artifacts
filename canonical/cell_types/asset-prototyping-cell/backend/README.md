# Asset Prototyping Cell – Backend

## Purpose

Python backend for the **Asset Prototyping Cell**. Provides the server-side pipeline logic for the 3-stage asset generation flow.

> ⚠️ **Note**: The `AssetPrototypingCell` frontend is deprecated in favor of `AssetPrototypingBook`. The backend scripts remain active as they are reused by the book implementation.

## Content Index

| Directory | Description |
|-----------|-------------|
| [`scripts/`](./scripts/) | `main.py` — Pipeline orchestration: text → PNG (Stable Diffusion) → SVG (Potrace) → 3D data |

## Related

- [`../`](../) — Asset Prototyping Cell root
- [`../frontend/`](../frontend/) — Frontend cell implementation (deprecated; use AssetPrototypingBook)
- [`../../png-generator-cell/`](../../png-generator-cell/) — PNG Generator Cell used in Stage 1
