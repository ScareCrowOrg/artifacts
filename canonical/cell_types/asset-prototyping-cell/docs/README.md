# Asset Prototyping Cell

## Overview

The Asset Prototyping Cell provides a complete pipeline for creating 3D assets from AI-generated images. It combines image generation, vectorization, and 3D prototyping in a single, integrated workflow with human validation checkpoints.

## Features

- **AI Image Generation**: Generate PNG images from text prompts using Stable Diffusion
- **SVG Vectorization**: Convert PNG images to clean SVG vectors
- **3D Prototyping**: Create 3D meshes with adjustable extrusion and bevel parameters
- **Human Validation**: Man-in-the-middle checkpoints for quality control
- **Real-time Preview**: Interactive Three.js viewport for immediate feedback

## Workflow Steps

### Step 1: PNG Generation

Generate a base image using AI:

1. Enter a descriptive prompt (e.g., "a sword with ornate handle")
2. Click "Generate PNG" to create the image
3. Review the generated image
4. Click "Approve & Continue" to proceed

**Technical Details:**
- Uses Stable Diffusion API (port 7860)
- Automatically enhances prompts for clean silhouettes
- Adds technical constraints for vectorization-friendly output
- White background and high contrast by default

### Step 2: SVG Vectorization

Convert the PNG to vector format using production-quality pipeline:

1. Review the selected PNG image
2. Click "Vectorize to SVG"
3. Preview the vectorized result
4. Click "Continue to 3D Prototyping"

**Technical Details:**
- **Production Pipeline**: OpenCV + Potrace for professional results
- **OpenCV Processing**: 
  - Otsu's automatic thresholding for optimal binary conversion
  - Morphological operations to remove noise and artifacts
- **Potrace Vectorization**:
  - Generates smooth Bézier curves ideal for 3D extrusion
  - Curve smoothing (alphamax 1.0) avoids sharp corners
  - Noise suppression removes small pixel islands
- **Output**: Clean SVG with Bézier paths optimized for Three.js ExtrudeGeometry

### Step 3: 3D Prototyping

Create and adjust the 3D mesh:

1. View the initial 3D mesh in the viewport
2. Adjust parameters:
   - **Depth**: Controls extrusion depth (1-50)
   - **Bevel Enabled**: Toggle bevel on/off
   - **Bevel Thickness**: Edge thickness (0-10)
   - **Bevel Size**: Bevel size (0-5)
   - **Bevel Segments**: Smoothness (1-10)
3. Use mouse to rotate/zoom the preview
4. Click "Export Asset" when satisfied

**Technical Details:**
- Uses Three.js with ExtrudeGeometry
- SVGLoader for path extraction
- OrbitControls for viewport interaction
- Real-time mesh regeneration on parameter change

## Properties

### currentStep (integer)
- Current workflow step (1, 2, or 3)
- Default: 1

### prompt (string)
- Text prompt for AI image generation
- Default: ""

### generatedPng (string | null)
- Base64-encoded PNG image data
- Default: null

### selectedPng (string | null)
- User-approved PNG for vectorization
- Default: null

### generatedSvg (string | null)
- Generated SVG markup code
- Default: null

### mesh3dConfig (object)
Configuration for Three.js ExtrudeGeometry:
- `depth`: Extrusion depth (default: 10)
- `bevelEnabled`: Enable bevel (default: true)
- `bevelThickness`: Bevel thickness (default: 2)
- `bevelSize`: Bevel size (default: 1)
- `bevelSegments`: Bevel segments (default: 3)

### isGenerating (boolean)
- Flag indicating PNG generation in progress
- Default: false

### isVectorizing (boolean)
- Flag indicating SVG vectorization in progress
- Default: false

### error (string | null)
- Error message if any operation fails
- Default: null

## API Integration

### Backend Services

**StableDiffusionService**
- Location: `backend/app/services/stable_diffusion_service.py`
- Endpoint: Configured via `STABLE_DIFFUSION_URL` (default: http://localhost:7860)
- Method: `txt2img` via `/sdapi/v1/txt2img`

**SVGVectorizationService**
- Location: `backend/app/services/svg_vectorization_service.py`
- **Production Pipeline**: OpenCV + Potrace
- **Image Processing**: Otsu thresholding + morphological noise removal
- **Vectorization**: Potrace with Bézier curve smoothing
- **Output**: High-quality SVG optimized for 3D extrusion

### Cell Execution

The cell orchestrates the workflow through `backend/scripts/main.py`:
- `generate_png()`: Step 1 handler
- `vectorize_png()`: Step 2 handler
- `validate_3d_config()`: Step 3 handler

## Configuration Requirements

### Environment Variables

Add to `.env`:
```bash
# Stable Diffusion Configuration
STABLE_DIFFUSION_URL=http://localhost:7860
STABLE_DIFFUSION_TIMEOUT=120
```

### System Requirements

**potrace Installation:**
```bash
# Ubuntu/Debian
sudo apt-get install potrace

# macOS
brew install potrace

# Windows
# Download from: http://potrace.sourceforge.net/
```

### Dependencies

**Backend (Python):**
- httpx - HTTP client for API calls
- opencv-python-headless - Image processing (binarization, morphology)
- Pillow (PIL) - Image I/O operations
- numpy - Numerical operations
- **potrace** - Binary executable for Bézier vectorization (system package)

**Frontend (JavaScript/TypeScript):**
- three - 3D rendering library
- three/examples/jsm/controls/OrbitControls - Viewport controls
- three/examples/jsm/loaders/SVGLoader - SVG parsing

## Usage Examples

### Basic Asset Creation

```typescript
// Create a simple weapon asset
const cellData = {
  currentStep: 1,
  prompt: "medieval sword with leather-wrapped handle",
  mesh3dConfig: {
    depth: 15,
    bevelEnabled: true,
    bevelThickness: 2,
    bevelSize: 1,
    bevelSegments: 3
  }
}
```

### Custom 3D Parameters

```typescript
// Create with custom extrusion
const cellData = {
  mesh3dConfig: {
    depth: 30,          // Deep extrusion
    bevelEnabled: true,
    bevelThickness: 5,  // Thick edges
    bevelSize: 3,       // Large bevel
    bevelSegments: 8    // Smooth curves
  }
}
```

## Validation Checkpoints

The cell enforces human validation at two critical points:

1. **After PNG Generation**: User must approve the generated image before vectorization
2. **After 3D Prototyping**: User must approve the 3D mesh before export

This ensures quality control and prevents automatic pipeline execution without human oversight.

## Limitations

1. **3D Export**: Export to Unity Addressables is planned but not yet implemented.

2. **Stable Diffusion Availability**: Requires a running Stable Diffusion instance on the configured port.

3. **Complex Shapes**: Very complex SVG paths may result in heavy 3D meshes. The pipeline applies automatic simplification and noise removal.

## Future Enhancements

- [ ] Export to Unity Addressables format
- [ ] Support for texture mapping
- [ ] Material and color customization
- [ ] Batch processing multiple assets
- [ ] Integration with 3D asset libraries
- [ ] Advanced color vectorization (currently grayscale)

## References

- [ADDING_NEW_CELL_TYPE.md](../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [RULESET.md](../../../docs/official/RULESET.md)
- [Three.js Documentation](https://threejs.org/docs/)
- [Stable Diffusion API](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API)

## Support

For issues or questions:
- Check the main ScareVerse documentation
- Review existing cell types for examples
- Contact the development team

---

**Last Updated**: 2026-01-15
**Version**: 1.0.0
**Status**: Implemented
