---
processed: true
processed_date: 2026-02-04
updated_docs:
  - docs/official/backend/architecture/content-contenttypes-system.md
themes:
  - content-types
  - canonical
  - architecture
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Content Types

## Overview

This directory contains canonical ContentType definitions that serve as blueprints for typed content assets in the ScareVerse system.

## Purpose

ContentTypes define the contract for content instances, providing:
- **Schema Definition**: Expected metadata fields (expected_fragments)
- **Rendering Hints**: Instructions for frontend visualization
- **Storage Policy**: Where raw data should be stored
- **Validation Rules**: File size limits, allowed extensions

## Structure

Each ContentType is defined in a JSON file following this naming convention:
- `<category>-<format>.json` (e.g., `image-png.json`, `3d-glb.json`)

## Available Content Types

- **image-png.json**: PNG image assets
- **vector-svg.json**: SVG vector graphics
- **3d-glb.json**: 3D models in GLB format

## Usage

ContentTypes are loaded by the ContentManager service and used to:
1. Validate Content instances before persistence
2. Enforce storage policies
3. Provide rendering hints to the frontend
4. Ensure metadata completeness

## Schema Format

```json
{
  "id": "unique-identifier",
  "name": "Human Readable Name",
  "mime_type": "type/subtype",
  "expected_fragments": {
    "required_field": {"type": "string"}
  },
  "render_hints": {
    "component": "VueComponentName"
  },
  "storage_policy": "local"
}
```
