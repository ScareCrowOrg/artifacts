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

The **SVG Generator Cell** is an interactive cell type that enables users to generate SVG visualizations from natural language descriptions using AI. This cell provides a simple yet powerful interface for creating graphics without manual SVG coding.

## Features

- **AI-Powered Generation**: Uses LLM (Large Language Model) to convert text descriptions into valid SVG code
- **Interactive Preview**: Real-time preview of generated SVG graphics
- **Export Options**: Copy SVG code to clipboard or download as `.svg` file
- **Code Visibility**: Toggle to view/hide the generated SVG source code
- **Dark Mode Support**: Full theme compliance with ScareVerse design system
- **Internationalized**: Supports English and Portuguese (pt-BR)
- **Keyboard Shortcuts**: Ctrl+Enter (Cmd+Enter on Mac) for quick generation

## Properties

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

### category (string)
- **Description**: Cell category - set to "ephemeral" (not persisted)
- **Default**: `"ephemeral"`

## Usage

### Basic Workflow

1. **Enter Description**: Type a text description of your desired SVG in the prompt field
2. **Generate**: Click the "Generate SVG" button or press Ctrl+Enter (Cmd+Enter)
3. **Preview**: View the generated SVG in the preview area
4. **Export**: Copy the SVG code or download it as a file

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

**Component**: `frontend/View.vue` (TypeScript)
- Vue 3 Composition API with TypeScript
- Theme-compliant styling using Tailwind CSS
- i18n integration for multilingual support
- API integration via `aiChatService`

### Backend Implementation

**Script**: `backend/scripts/main.py`
- Main execution function: `execute_cell(cell_data)`
- SVG generation function: `generate_svg_from_prompt(prompt, model)`
- Uses LLMService for AI-powered generation
- Error handling and validation

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
├── type.json                    # Symlink to canonical type definition
├── backend/
│   ├── scripts/
│   │   ├── __init__.py
│   │   └── main.py             # SVG generation logic
│   └── tests/
│       └── test_main.py        # Backend tests
├── frontend/
│   ├── View.vue                # Main Vue component (TypeScript)
│   └── tests/
│       └── View.spec.ts        # Frontend tests
└── docs/
    └── README.md               # This file
```

## Testing

### Manual Testing

1. Start the ScareVerse backend and frontend
2. Create a new SVG Generator cell instance
3. Enter a prompt and generate an SVG
4. Verify the SVG renders correctly
5. Test copy and download functionality

### Automated Tests

**Backend Tests**: Located in `backend/tests/test_main.py`
- Test `execute_cell()` function
- Test SVG generation logic
- Test error handling

**Frontend Tests**: Located in `frontend/tests/View.spec.ts`
- Test component rendering
- Test user interactions
- Test API integration
- Test error states

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

- [ADDING_NEW_CELL_TYPE.md](../../official/ADDING_NEW_CELL_TYPE.md) - Cell type creation guide
- [RULESET.md](../../official/RULESET.md) - Project rules and standards
- [TEAM.md](../../official/TEAM.md) - Team workflow and responsibilities

## Support

For issues or questions:
- Create an issue in the ScareVerse repository
- Tag with `cell-type` and `svg-generator` labels
- Include prompt and error details

---

**Version**: 1.0.0  
**Created**: 2026-01-13  
**Category**: visualization  
**Status**: Active
