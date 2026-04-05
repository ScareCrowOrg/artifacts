---
processed: true
processed_date: 2026-01-15
generated_docs:
  - docs/official/backend/cell-types/asset-prototyping-cell.md
themes:
  - cell-types
  - 3d
  - threejs
  - scene-generation
modules:
  - artifacts
  - frontend
code_verified: true
dead_docs_found: false
---
# Three.js Scene Generator Cell

## Overview

The **Three.js Scene Generator Cell** is an interactive cell type that enables users to generate and prototype 3D scenes using Three.js library from natural language descriptions. This cell is designed to be the first component of the "Asset Prototyping Book" in ScareVerse, allowing rapid prototyping of 3D content through AI-assisted code generation.

## Features

- 🎨 **AI-Powered Generation**: Generate Three.js code from natural language descriptions
- 🎭 **Real-time 3D Preview**: View generated scenes rendered directly in the cell
- 📝 **Code Display**: View and edit the generated Three.js JavaScript code
- 💾 **Export Functionality**: Copy or download generated scripts
- 🌓 **Dark Mode Support**: Fully compatible with ScareVerse's theme system
- 🌍 **Internationalized**: Support for English and Portuguese

## Properties

### prompt (string)
- **Description**: Text description of the desired 3D scene
- **Default**: `""`
- **Example**: "A rotating cube with metallic material and dynamic lighting"

### generatedScript (string | null)
- **Description**: Generated Three.js JavaScript code
- **Default**: `null`
- **Format**: Plain JavaScript code using Three.js API

### isGenerating (boolean)
- **Description**: Flag indicating if scene generation is in progress
- **Default**: `false`

### error (string | null)
- **Description**: Error message if generation fails
- **Default**: `null`

### selectedModel (string)
- **Description**: Selected AI model for code generation
- **Default**: `"mistral"`
- **Options**: Dynamic based on available models (local and external)

### category (string)
- **Description**: Cell category - set to 'ephemeral' (not persisted)
- **Default**: `"ephemeral"`

## Usage

### Creating a Cell Instance

1. Open a notebook in ScareVerse
2. Add a new cell
3. Select "Three.js Scene Generator Cell" from the cell type dropdown
4. The cell will be created with default properties

### Generating a 3D Scene

1. Enter a description of your desired 3D scene in the prompt field
2. Select an AI model from the dropdown (optional)
3. Click "Generate 3D Scene" or press Ctrl+Enter (Cmd+Enter on Mac)
4. Wait for the generation to complete
5. The 3D scene will render in the preview area
6. View the generated code by clicking "Show Three.js Code"

### Example Prompts

**Simple Geometry**:
- "A rotating red cube in the center"
- "A blue sphere with a golden torus around it"
- "Three colorful pyramids arranged in a triangle"

**Advanced Scenes**:
- "A solar system with planets orbiting the sun"
- "A forest scene with trees and fog"
- "An abstract geometric sculpture with dynamic lighting"

**Interactive Elements**:
- "A spinning cube that changes color when clicked"
- "A bouncing ball with realistic physics"
- "A particle system creating a galaxy effect"

## Architecture

### Frontend (TypeScript)

**File**: `frontend/View.vue`

The frontend component is built with Vue 3 Composition API and TypeScript, following ScareVerse's coding standards (RULESET.md Rule 4.5).

**Key Components**:
- Model selection dropdown
- Prompt input textarea
- Generate button with loading state
- Error display
- 3D canvas container for scene rendering
- Code display with syntax highlighting
- Copy/download functionality

**Three.js Integration**:
- Loads Three.js library from CDN (v0.160.0)
- Executes generated code in controlled environment
- Manages scene lifecycle and cleanup
- Handles window resize events

### Backend (Python)

**File**: `backend/scripts/main.py`

The backend provides the execution logic and LLM integration for code generation.

**Key Functions**:

#### `execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]`
Executes the cell and returns status information.

#### `generate_threejs_from_prompt(prompt: str, model: str) -> Dict[str, Any]`
Generates Three.js code from a text prompt using LLM service.

**Integration**:
- Uses `LLMService` for AI code generation
- Implements specialized system instructions for Three.js
- Validates generated code for Three.js elements
- Handles errors gracefully

## Technical Details

### Dependencies

**Frontend**:
- Vue 3
- TypeScript
- Three.js (loaded from CDN: https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js)
- aiChatService for model selection and generation

**Backend**:
- Python 3.8+
- LLMService (ScareVerse backend service)

### Code Generation Strategy

The cell uses a specialized system instruction prompt that guides the LLM to generate:
1. Complete, self-contained Three.js scenes
2. Proper scene setup (scene, camera, renderer)
3. Appropriate lighting (ambient + directional)
4. Animation loops using requestAnimationFrame
5. Window resize handlers
6. Well-commented, production-ready code

### Security Considerations

- Generated code is executed in a controlled environment
- No direct access to DOM outside the canvas container
- Three.js library is loaded from trusted CDN
- Code validation before execution
- Timeout mechanisms to prevent infinite loops

## Testing

### Frontend Tests

**File**: `frontend/tests/View.spec.ts`

Run frontend tests:
```bash
cd cockpit-vue
npm test -- artifacts/canonical/cell_types/threejs-scene-generator-cell/frontend/tests/
```

### Backend Tests

**File**: `backend/tests/test_main.py`

Run backend tests:
```bash
cd backend
poetry run pytest artifacts/canonical/cell_types/threejs-scene-generator-cell/backend/tests/
```

## Internationalization

The cell supports multiple languages through Vue i18n:

- **English (en-US)**: Full support
- **Portuguese (pt-BR)**: Full support

Translation keys are defined in:
- `cockpit-vue/src/i18n/locales/en-US.json`
- `cockpit-vue/src/i18n/locales/pt-BR.json`

## Future Enhancements

### Planned Features

1. **Code Editor Integration**: Monaco Editor for advanced code editing
2. **Scene Templates**: Pre-built scene templates for quick start
3. **Material Library**: Built-in materials and textures
4. **Camera Controls**: Interactive camera movement (OrbitControls)
5. **Export Formats**: Export to glTF, OBJ, or other 3D formats
6. **Physics Integration**: Support for physics engines (Cannon.js, Ammo.js)
7. **Post-Processing**: Effects like bloom, SSAO, depth of field
8. **VR/AR Support**: WebXR integration for immersive experiences

### Roadmap Integration

This cell is the first component of the **Asset Prototyping Book** initiative:

1. ✅ **Phase 1**: Three.js Scene Generator (Current)
2. **Phase 2**: Blender Script Generator Cell

4. **Phase 4**: Integrated Asset Pipeline

## Troubleshooting

### Scene Not Rendering

**Problem**: 3D scene doesn't appear after generation

**Solutions**:
1. Check browser console for Three.js loading errors
2. Verify generated code contains required Three.js elements
3. Ensure container element is properly mounted
4. Check for JavaScript errors in generated code

### Generation Errors

**Problem**: Code generation fails or produces invalid code

**Solutions**:
1. Simplify the prompt description
2. Try a different AI model
3. Check backend logs for LLM service errors
4. Verify model is properly configured and accessible

### Performance Issues

**Problem**: Scene rendering is slow or janky

**Solutions**:
1. Reduce scene complexity (fewer objects, simpler geometry)
2. Optimize materials (use simpler shaders)
3. Lower animation frame rate
4. Check for memory leaks in animation loop

## References

### ScareVerse Documentation
- [ADDING_NEW_CELL_TYPE.md](../../../../docs/official/ADDING_NEW_CELL_TYPE.md) - Cell creation guide
- [RULESET.md](../../../../docs/official/RULESET.md) - Project coding standards
- [TEAM.md](../../../../docs/official/TEAM.md) - Team structure and workflow

### External Resources
- [Three.js Documentation](https://threejs.org/docs/)
- [Three.js Examples](https://threejs.org/examples/)
- [WebGL Fundamentals](https://webglfundamentals.org/)

## Support

For issues or questions:
- Open an issue with tag `cell-type:threejs-scene-generator`
- Contact the development team
- Consult the documentation references above

---

**Version**: 1.0.0  
**Category**: prototyping, 3d-assets  
**Status**: Active  
**Last Updated**: 2026-01-14
