---
processed: true
processed_date: 2026-01-15
generated_docs:
  - docs/official/backend/cell-types/png-generator-cell.md
themes:
  - cell-types
  - ai-integration
  - image-generation
  - stable-diffusion
modules:
  - artifacts
  - backend
code_verified: true
dead_docs_found: false
---
# PNG Generator Cell

## Overview

The **PNG Generator Cell** is an interactive cell type that enables users to generate PNG images from natural language descriptions using Stable Diffusion AI. This cell provides a powerful yet intuitive interface for creating visual content directly within the ScareVerse platform.

## Features

- **AI-Powered Image Generation**: Uses Stable Diffusion to convert text descriptions into high-quality PNG images
- **Configurable Parameters**: Adjust image dimensions, generation steps, and guidance scale
- **Interactive Preview**: Real-time display of generated images
- **Export Options**: Copy image to clipboard or download as `.png` file
- **Dark Mode Support**: Full theme compliance with ScareVerse design system
- **Internationalized**: Supports English and Portuguese (pt-BR)
- **Keyboard Shortcuts**: Ctrl+Enter (Cmd+Enter on Mac) for quick generation

## Properties

### prompt (string)
- **Description**: Text description of the desired image
- **Default**: `""`
- **Example**: "A majestic red dragon flying over mountains at sunset"

### generatedPng (string | null)
- **Description**: Base64-encoded PNG image data (data URI format)
- **Default**: `null`
- **Notes**: Populated after successful generation

### isGenerating (boolean)
- **Description**: Flag indicating if image generation is in progress
- **Default**: `false`

### error (string | null)
- **Description**: Error message if generation fails
- **Default**: `null`

### generationParams (object)
Configuration parameters for Stable Diffusion:
- **width** (number): Image width in pixels (256-1024, step 64, default: 512)
- **height** (number): Image height in pixels (256-1024, step 64, default: 512)
- **steps** (number): Number of denoising steps (10-50, default: 20)
- **cfg_scale** (number): Classifier-free guidance scale (1-20, default: 7.0)
- **seed** (number): Random seed for reproducibility (-1 for random, default: -1)

### category (string)
- **Description**: Cell category - set to "ephemeral" (not persisted)
- **Default**: `"ephemeral"`

## Usage

### Basic Workflow

1. **Enter Description**: Type a text description of your desired image in the prompt field
2. **Configure Parameters** (optional): Adjust width, height, steps, and CFG scale
3. **Generate**: Click the "Generate PNG" button or press Ctrl+Enter (Cmd+Enter)
4. **Preview**: View the generated image in the preview area
5. **Export**: Copy the image to clipboard or download it as a file

### Example Prompts

**Landscapes**:
- "A serene mountain landscape with snow-capped peaks at golden hour"
- "A tropical beach with crystal clear water and palm trees"
- "A misty forest with rays of sunlight breaking through the canopy"

**Characters**:
- "A futuristic cyborg warrior with glowing blue eyes"
- "A wise old wizard with a long white beard and starry robes"
- "A cute robot companion with friendly LED eyes"

**Objects**:
- "A ornate fantasy sword with glowing runes on the blade"
- "A steampunk airship with brass gears and propellers"
- "A magical crystal emitting ethereal light"

**Abstract**:
- "Abstract geometric patterns in vibrant neon colors"
- "Swirling galaxies and nebulae in deep space"
- "Flowing liquid metal with rainbow reflections"

### Tips for Better Results

1. **Be Descriptive**: Include details about colors, lighting, composition, and style
2. **Use Adjectives**: Descriptive words like "majestic", "serene", "vibrant" improve quality
3. **Specify Style**: Mention art styles like "photorealistic", "anime", "oil painting", "digital art"
4. **Lighting Matters**: Describe lighting conditions like "golden hour", "dramatic lighting", "soft diffused light"
5. **Adjust Steps**: More steps (30-50) generally produce higher quality but take longer
6. **CFG Scale**: Higher values (10-15) follow the prompt more closely, lower values (5-7) allow more creativity
7. **Fixed Seed**: Use a specific seed (not -1) to reproduce the same image with slight variations

## Technical Details

### Frontend Implementation

**Component**: `frontend/View.vue` (TypeScript)
- Vue 3 Composition API with TypeScript for type safety
- Theme-compliant styling using Tailwind CSS utility classes
- i18n integration for multilingual support
- Reactive state management with Vue refs
- Event emission for parent component communication

### Backend Implementation

**Script**: `backend/scripts/main.py`
- Main execution function: `execute_cell(cell_data)`
- PNG generation function: `generate_png_from_prompt(prompt, ...params)`
- Uses `StableDiffusionService` for image generation
- Comprehensive error handling and validation

### API Communication

The cell integrates with the existing Stable Diffusion service through the `StableDiffusionService` class:

1. Frontend emits generation request with prompt and parameters
2. Backend calls `StableDiffusionService.generate_image()`
3. Service communicates with Stable Diffusion API (default: `http://localhost:7860`)
4. Generated image returned as base64-encoded PNG
5. Frontend displays image in preview area

### Generation Parameters

**Width & Height**:
- Supported range: 256-1024 pixels (step: 64)
- Common sizes: 512x512, 768x768, 512x768 (portrait), 768x512 (landscape)
- Larger sizes require more VRAM and processing time

**Steps**:
- Number of denoising iterations
- Range: 10-50 steps
- Recommended: 20-30 for most use cases
- More steps = higher quality but slower generation

**CFG Scale** (Classifier-Free Guidance):
- Controls how closely the model follows the prompt
- Range: 1-20
- Recommended: 7-9 for balanced results
- Higher values: stricter adherence to prompt
- Lower values: more creative freedom

**Seed**:
- Random number generator seed
- Value: -1 (random) or specific integer
- Same seed + prompt = reproducible results
- Useful for iterating on successful generations

## Directory Structure

```
png-generator-cell/
├── type.json                    # 🔗 SYMLINK → ../../notebook_item_types/png-generator-cell.json
├── backend/
│   ├── scripts/
│   │   ├── __init__.py
│   │   └── main.py             # PNG generation logic
│   └── tests/
│       └── test_main.py        # Backend tests (pytest)
├── frontend/
│   ├── View.vue                # Main Vue component (TypeScript)
│   └── tests/
│       └── View.spec.ts        # Frontend tests (Vitest)
└── docs/
    └── README.md               # This file
```

### Type Definition (Symlink Architecture)

The `type.json` in this directory is a **symlink** pointing to the canonical definition:
```
../../notebook_item_types/png-generator-cell.json
```

**Important**: To modify the cell type definition, edit the canonical file in `notebook_item_types/`, not the symlink. This ensures consistency and follows the ScareVerse symlink architecture pattern.

**Why Symlinks?**
- **Single Source of Truth**: The canonical definition in `notebook_item_types/` is the only place to edit
- **Automatic Propagation**: Changes are immediately reflected everywhere via symlink
- **Clear Ownership**: Registry reads from canonical source
- **No Duplication**: Eliminates sync issues between multiple definitions

For more information, see [Cell Type Symlink Architecture](../../../../docs/official/backend/architecture/cell-type-symlink-architecture.md).

## Testing

### Manual Testing

1. Start the ScareVerse backend and frontend applications
2. Ensure Stable Diffusion service is running (port 7860)
3. Create a new PNG Generator cell instance
4. Enter a descriptive prompt
5. Adjust generation parameters if desired
6. Generate and verify the image renders correctly
7. Test copy to clipboard functionality
8. Test download functionality
9. Test with different prompts and parameters

### Automated Tests

**Backend Tests**: Located in `backend/tests/test_main.py`
- Test `execute_cell()` function with various inputs
- Test `generate_png_from_prompt()` function
- Test error handling and edge cases
- Mock Stable Diffusion service responses
- Validate parameter passing

**Frontend Tests**: Located in `frontend/tests/View.spec.ts`
- Test component rendering and structure
- Test user interactions (typing, clicking, keyboard shortcuts)
- Test prop updates and event emissions
- Test parameter validation
- Test error states and loading states
- Test preview display and export functions

**Running Tests**:
```bash
# Backend tests
cd backend
poetry run pytest artifacts/canonical/cell_types/png-generator-cell/backend/tests/

# Frontend tests
cd cockpit-vue
npm run test artifacts/canonical/cell_types/png-generator-cell/frontend/tests/
```

## Integration

The PNG Generator Cell is automatically discovered by the ScareVerse backend on startup. No manual registration is required.

### Discovery Process

1. Backend scans `artifacts/canonical/cell_types/` directory
2. Finds `type.json` with cell type definition
3. Validates cell type structure and schema
4. Registers cell type in MongoDB database
5. Makes cell type available via API to frontend

## Configuration

### Stable Diffusion Service

The cell requires a Stable Diffusion service to be running. Configuration is managed through environment variables in `backend/.env`:

```env
STABLE_DIFFUSION_URL=http://localhost:7860
STABLE_DIFFUSION_TIMEOUT=120
```

**Default URL**: `http://localhost:7860` (standard Stable Diffusion web UI port)
**Timeout**: 120 seconds (configurable for slow generations)

### Starting Stable Diffusion

Refer to the infrastructure documentation for starting the Stable Diffusion service:
- Local: `infrastructure/local/kubernetes/base/services/sd-api/`
- Docker: Use the provided docker-compose configuration

## Troubleshooting

### Cell Not Appearing

- **Check Backend Logs**: Ensure cell type was discovered during startup
- **Verify Directory Structure**: Confirm all required files exist
- **Restart Backend**: Trigger re-discovery of cell types

### Generation Fails

- **Check SD Service**: Verify Stable Diffusion is running and accessible
  ```bash
  curl http://localhost:7860/sdapi/v1/sd-models
  ```
- **Review Backend Logs**: Check for connection errors or timeouts
- **Verify Configuration**: Ensure `STABLE_DIFFUSION_URL` is correct
- **Check Parameters**: Ensure width/height are within supported range
- **Simplify Prompt**: Try a simpler description to isolate issues

### Image Not Displaying

- **Check Console**: Look for errors in browser developer console
- **Verify Base64**: Ensure generated PNG data is valid base64
- **Check Format**: Confirm data URI starts with `data:image/png;base64,`

### Slow Generation

- **Reduce Steps**: Lower the steps parameter (try 15-20)
- **Smaller Size**: Use 512x512 instead of larger dimensions
- **Check Resources**: Verify Stable Diffusion has adequate GPU/CPU resources
- **Timeout Settings**: Increase `STABLE_DIFFUSION_TIMEOUT` if needed

### Memory Issues

- **Lower Resolution**: Use smaller image dimensions
- **Batch Size**: Stable Diffusion configuration - reduce if OOM errors occur
- **Clear VRAM**: Restart Stable Diffusion service to clear GPU memory

## Limitations

1. **Dependencies**: Requires external Stable Diffusion service to be running
2. **Generation Time**: Image generation can take 10-60 seconds depending on parameters
3. **VRAM Requirements**: High-resolution images require significant GPU memory
4. **Prompt Interpretation**: Results may vary based on model and prompt clarity
5. **Network Latency**: Generation time affected by network speed to SD service

## Future Enhancements

Potential improvements for future versions:

- **Negative Prompts**: UI for specifying what to avoid in generation
- **Style Presets**: Predefined styles (photorealistic, anime, oil painting, etc.)
- **Seed Control**: UI for setting specific seeds for reproducibility
- **History**: Save and reuse previous prompts and parameters
- **Batch Generation**: Generate multiple variations at once
- **Img2Img**: Use existing image as starting point for generation
- **Inpainting**: Edit specific regions of generated images
- **ControlNet**: Additional control over composition and structure
- **Model Selection**: Choose between different Stable Diffusion models
- **Progress Indicator**: Real-time progress updates during generation

## References

- [ADDING_NEW_CELL_TYPE.md](../../../docs/official/ADDING_NEW_CELL_TYPE.md) - Cell type creation guide
- [RULESET.md](../../../docs/official/RULESET.md) - Project rules and standards
- [TEAM.md](../../../docs/official/TEAM.md) - Team workflow and responsibilities
- [Stable Diffusion Service](../../../backend/app/services/stable_diffusion_service.py) - Service implementation
- [SVG Generator Cell](../svg-generator-cell/docs/README.md) - Related cell type
- [Asset Prototyping Cell](../../notebook_item_types/asset-prototyping-cell.json) - Related asset type

## Support

For issues or questions:
- Create an issue in the ScareVerse repository
- Tag with `cell-type` and `png-generator` labels
- Include prompt, parameters, and error details
- Attach screenshots if applicable

---

**Version**: 1.0.0  
**Created**: 2026-01-15  
**Category**: visualization  
**Status**: Active  
**Dependencies**: Stable Diffusion Service
