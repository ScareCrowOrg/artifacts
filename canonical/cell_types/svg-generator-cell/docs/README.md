---
processed: true
processed_date: 2026-01-15
generated_docs:
  - docs/official/backend/cell-types/asset-prototyping-cell.md
themes:
  - cell-types
  - vectorization
  - svg
  - image-processing
modules:
  - artifacts
  - backend
code_verified: true
dead_docs_found: false
---
# SVG Generator Cell

## Overview

The **SVG Generator Cell** is a BaseCell-compliant cell type that enables users to generate SVG visualizations from natural language descriptions using AI. This cell implements the BaseCell v1.0 interface for headless execution, composability, and standardized lifecycle management.

## Architecture

**BaseCell Implementation**: ✅ Fully compliant with BaseCell v1.0 Framework

### Key Components

- **Frontend**: `SvgGeneratorCell.ts` - TypeScript class implementing `BaseCell` interface
- **UI Component**: `View.vue` - Vue 3 component for user interaction
- **Backend**: `main.py` - Python execution logic (optional, uses LLM service)
- **Tests**: Comprehensive unit tests with 90%+ coverage

### BaseCell Interface

The cell implements all required BaseCell methods:
- `execute(input)` - Generate SVG from text prompt
- `describe()` - Return cell metadata and capabilities
- `validate(input)` - Validate input parameters

Optional lifecycle methods:
- `health_check()` - Monitor LLM service availability

## Features

- **BaseCell-Compliant**: Implements standardized execution interface
- **Headless Execution**: Can be executed programmatically without UI
- **AI-Powered Generation**: Uses LLM (Large Language Model) to convert text descriptions into valid SVG code
- **Fallback Mechanism**: Gracefully degrades to placeholder SVG when LLM unavailable
- **Interactive Preview**: Real-time preview of generated SVG graphics
- **Export Options**: Copy SVG code to clipboard or download as `.svg` file
- **Code Visibility**: Toggle to view/hide the generated SVG source code
- **Model Selection**: Support for multiple LLM models (local/cloud/BYOK)
- **Dark Mode Support**: Full theme compliance with ScareVerse design system
- **Internationalized**: Supports English and Portuguese (pt-BR)
- **Keyboard Shortcuts**: Ctrl+Enter (Cmd+Enter on Mac) for quick generation

## BaseCell API

### Input Schema (execute method)

```typescript
{
  prompt: string,           // Required: Text description of desired SVG
  model?: string,           // Optional: LLM model (default: 'mistral')
  temperature?: number,     // Optional: 0.0-1.0 (default: 0.7)
  maxTokens?: number        // Optional: 100-10000 (default: 2000)
}
```

### Output Schema

```typescript
{
  svg: string,              // Generated SVG code
  prompt: string,           // Original prompt
  model: string,            // Model used
  fallback?: boolean        // True if fallback SVG was used
}
```

### Validation Rules

- `prompt`: Required, non-empty string, max 5000 characters
- `model`: Optional string (default: 'mistral')
- `temperature`: Optional number between 0 and 1
- `maxTokens`: Optional number between 100 and 10000

## Properties (Legacy - for UI compatibility)

### prompt (string)
- **Description**: Text description of the desired SVG visualization
- **Default**: `""`
- **Example**: "A blue circle with radius 50, centered in a 200x200 viewBox"

### generatedSvg (string | null)
- **Description**: The generated SVG markup code
- **Default**: `null`
- **Notes**: Populated after successful generation

### isGenerating (boolean)
- **Description**: Flag indicating if SVG generation is in progress
- **Default**: `false`

### error (string | null)
- **Description**: Error message if generation fails
- **Default**: `null`

### selectedModel (string)
- **Description**: Currently selected LLM model
- **Default**: `"mistral"`

### category (string)
- **Description**: Cell category - set to "visualization"
- **Default**: `"visualization"`

## Usage

### Headless Execution (via BaseCell)

```typescript
import { SvgGeneratorCell } from './SvgGeneratorCell'

const svgCell = new SvgGeneratorCell()

// Execute headless
const result = await svgCell.execute({
  prompt: 'A blue circle with radius 50',
  model: 'mistral'
})

if (result.success) {
  console.log('Generated SVG:', result.output.svg)
  console.log('Execution time:', result.execution_time, 'ms')
}
```

### Validation Example

```typescript
// Validate before execution
const errors = svgCell.validate({
  prompt: 'A red square'
})

if (errors.length === 0) {
  const result = await svgCell.execute({ prompt: 'A red square' })
}
```

### Health Check Example

```typescript
// Check if LLM service is available
const health = await svgCell.health_check()

if (health.status === 'healthy') {
  console.log('Service ready with', health.metadata.available_models, 'models')
} else if (health.status === 'degraded') {
  console.log('Service degraded - will use fallback')
}
```

### UI Workflow

1. **Enter Description**: Type a text description of your desired SVG in the prompt field
2. **Select Model**: Choose an available LLM model from dropdown
3. **Generate**: Click the "Generate SVG" button or press Ctrl+Enter (Cmd+Enter)
4. **Preview**: View the generated SVG in the preview area
5. **Export**: Copy the SVG code or download it as a file

### Example Prompts

**Simple Shapes**:
- "A red circle with a 50px radius"
- "A blue rectangle 200x100 with rounded corners"
- "A yellow star with 5 points"

**Complex Graphics**:
- "A bar chart showing values 10, 25, 15, 30 with blue bars"
- "A simple house icon with a triangle roof and rectangle body"
- "A progress indicator showing 75% completion in green"

**Icons and Symbols**:
- "A check mark icon in green"
- "A warning triangle with an exclamation mark"
- "A heart shape filled with red color"

### Tips for Better Results

1. **Be Specific**: Include details about shapes, colors, sizes, and positions
2. **Mention ViewBox**: Specify dimensions like "in a 200x200 viewBox" for consistent sizing
3. **Simple First**: Start with simple shapes and build complexity gradually
4. **Color Names**: Use standard color names (red, blue, green) or hex codes (#FF0000)
5. **Proportions**: Describe relative sizes and positions clearly

## Technical Details

### Frontend Implementation

**BaseCell Class**: `frontend/SvgGeneratorCell.ts` (TypeScript)
- Implements `BaseCell` interface from `@/types/BaseCell`
- Core execution logic with LLM integration
- Input validation and health checking
- Fallback mechanism for service failures

**UI Component**: `frontend/View.vue` (TypeScript)
- Vue 3 Composition API with TypeScript
- Uses `SvgGeneratorCell` class for execution
- Theme-compliant styling using Tailwind CSS
- i18n integration for multilingual support
- Model selection and configuration UI

### Backend Implementation (Optional)

**Script**: `backend/scripts/main.py`
- Main execution function: `execute_cell(cell_data)`
- SVG generation function: `generate_svg_from_prompt(prompt, model)`
- Uses LLMService for AI-powered generation
- Error handling and validation
- **Note**: Frontend primarily executes via aiChatService; backend is optional fallback

### API Communication

The cell uses the existing chat API endpoint (`/api/chat/processar`) with a specialized prompt that instructs the LLM to:
1. Generate only SVG code (no explanations)
2. Start with `<svg>` and end with `</svg>`
3. Include proper `viewBox` and dimensions
4. Use clean, readable SVG structure

### SVG Validation

Generated content is validated to ensure:
- Starts with `<svg>` tag
- Contains valid SVG markup
- Can be rendered in browser

## Directory Structure

```
svg-generator-cell/
├── type.json                        # Symlink to canonical type definition
├── backend/
│   ├── scripts/
│   │   ├── __init__.py
│   │   └── main.py                 # SVG generation logic (optional)
│   └── tests/
│       └── test_main.py            # Backend tests
├── frontend/
│   ├── SvgGeneratorCell.ts         # BaseCell implementation (TypeScript)
│   ├── View.vue                    # UI component (Vue 3 + TypeScript)
│   └── tests/
│       ├── README.md               # Test documentation
│       ├── SvgGeneratorCell.test.ts # BaseCell unit tests
│       └── View.spec.ts            # Component tests
└── docs/
    └── README.md                   # This file
```

## Testing

### Test Coverage: 90%+ (RULESET.md compliant)

### Automated Tests

**BaseCell Unit Tests**: `frontend/tests/SvgGeneratorCell.test.ts`
- ✅ Execution tests with valid/invalid inputs
- ✅ Validation rule tests
- ✅ Metadata and capabilities tests
- ✅ Health check tests (service availability)
- ✅ Fallback mechanism tests
- ✅ Integration workflow tests
- **Coverage**: 90%+ of BaseCell implementation

**Component Tests**: `frontend/tests/View.spec.ts`
- Test Vue component rendering
- Test user interactions
- Test model selection
- Test error states and fallback display

**Backend Tests**: `backend/tests/test_main.py`
- Test `execute_cell()` function
- Test SVG generation logic
- Test error handling

### Running Tests

```bash
# Run all svg-generator-cell tests
npm run test:unit -- svg-generator-cell

# Run with coverage report
npm run test:coverage

# Watch mode for development
npm run test:watch
```

### Manual Testing

1. **Headless Execution Test**:
   ```typescript
   const cell = new SvgGeneratorCell()
   const result = await cell.execute({ prompt: 'A red circle' })
   console.log(result)
   ```

2. **UI Integration Test**:
   - Start the ScareVerse backend and frontend
   - Create a new SVG Generator cell instance
   - Enter a prompt and generate an SVG
   - Verify the SVG renders correctly
   - Test copy and download functionality

3. **Health Check Test**:
   ```typescript
   const health = await cell.health_check()
   console.log('Service status:', health.status)
   ```

## Integration

The SVG Generator Cell is automatically discovered by the ScareVerse backend on startup. No manual registration is required.

### Discovery Process

1. Backend scans `artifacts/canonical/cell_types/` directory
2. Finds `type.json` (symlink to canonical definition)
3. Validates cell type structure
4. Registers cell type in database
5. Makes available via API to frontend

## Troubleshooting

### Cell Not Appearing

- **Check Backend Logs**: Ensure cell type was discovered
- **Verify Symlink**: Confirm `type.json` symlink is valid
- **Restart Backend**: Trigger re-discovery

### Generation Fails

- **Check API Key**: Ensure OpenAI API key is configured
- **Verify Model**: Confirm selected model is available
- **Check Logs**: Review backend logs for errors
- **Simplify Prompt**: Try a simpler description

### SVG Not Rendering

- **Validate SVG**: Check if generated code is valid SVG
- **Browser Console**: Look for rendering errors
- **ViewBox**: Ensure SVG has proper viewBox attribute

## Configuration

### Model Selection

The cell uses GPT-4 by default for high-quality SVG generation. This can be configured in the backend by modifying the `generate_svg_from_prompt()` function.

### Temperature Setting

Currently set to `0.7` for balanced creativity and consistency. Can be adjusted in `backend/scripts/main.py`.

### Token Limits

Maximum tokens set to `2000` to accommodate detailed SVG descriptions.

## Limitations

1. **Complexity**: Very complex visualizations may require multiple iterations
2. **Consistency**: Generated SVGs may vary slightly between runs
3. **Size**: Large SVGs (many elements) may hit token limits
4. **Interactivity**: Generated SVGs are static (no animations or interactions)

## Future Enhancements

Potential improvements for future versions:

- **Style Presets**: Predefined styles (minimal, colorful, corporate)
- **Size Templates**: Common SVG dimensions (icon, banner, card)
- **History**: Save and reuse previous prompts
- **Refinement**: Iterate on generated SVGs with additional instructions
- **Batch Generation**: Generate multiple variations at once
- **Animation**: Add simple CSS animations to generated SVGs

## References

### BaseCell Framework
- [BaseCell Interface](../../../../cockpit-vue/src/types/BaseCell.ts) - TypeScript interface definition
- [ADDING_NEW_CELL_TYPE.md](../../../docs/official/ADDING_NEW_CELL_TYPE.md) - Cell type creation guide
- [BaseCell v1.0 Planning](../../../docs/issues/base-cell-v1-implementation/) - Architecture details

### Project Standards
- [RULESET.md](../../../docs/official/RULESET.md) - Project rules and standards (Rule 4.8)
- [TEAM.md](../../../docs/official/TEAM.md) - Team workflow and responsibilities
- [Test Architecture](../../../docs/official/standards/ARQUITETURA_TESTES.md) - Testing standards

### Related Cells
- [CalculatorCell](../../calculator-cell/) - Pure frontend BaseCell example
- [ContentManagerCell](../../content-manager-cell/) - Backend-delegated BaseCell example

## Support

For issues or questions:
- Create an issue in the ScareVerse repository
- Tag with `cell-type` and `svg-generator` labels
- Include prompt and error details

---

**Version**: 2.0.0  
**Created**: 2026-01-13  
**Updated**: 2026-02-09 (BaseCell Migration)  
**Category**: visualization  
**BaseCell Compliance**: ✅ Fully compliant with BaseCell v1.0  
**Test Coverage**: 90%+  
**Status**: Active
