# Asset Prototyping Cell – Backend Scripts

## Purpose

Backend entry point for the **Asset Prototyping Cell** pipeline. Orchestrates the 3-stage asset generation flow: text-to-PNG (Stable Diffusion) → PNG-to-SVG (vectorization) → 3D prototyping data (Three.js).

## Content Index

| File | Description |
|------|-------------|
| [`main.py`](./main.py) | Pipeline orchestration — `generate_png()`, `vectorize_to_svg()`, `prepare_3d_data()` async functions; integrates with `StableDiffusionService` and `PotraceDependency` |

## Pipeline

```
Text Prompt → [Stable Diffusion] → PNG → [Potrace] → SVG → [Three.js] → 3D Data
```

## Related

- [`../`](../) — Asset Prototyping Cell backend root
- [`../../png-generator-cell/`](../../png-generator-cell/) — PNG Generator Cell (used for Stage 1)
