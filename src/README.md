# Artifacts — Src

Source asset directory for the ScareVerseLab artifacts layer.
Contains raw source files (styles, templates, etc.) that are processed or
compiled before being consumed by cells and the platform frontend.

## Purpose

Provides version-controlled source assets that feed the build pipeline.
These files are the **editable originals** — the compiled outputs are
distributed to individual cell packages or the frontend host.

## Content Index

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `styles/` | Global CSS/SCSS source files — design tokens, reset styles, and shared theme variables used by all cell types (see [styles/README.md](./styles/README.md)) |

## Related Documentation

- [Artifacts Root](../README.md) — canonical, runtime, dev, and shared artifact directories
- [Shared Styles](../shared/styles/) — compiled/distributed style utilities consumed at runtime
