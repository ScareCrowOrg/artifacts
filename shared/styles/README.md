---
processed: true
processed_date: 2025-12-11
generated_docs:
  - docs/official/frontend/design-system/theme-system.md
  - docs/official/frontend/design-system/components-utilities.md
themes:
  - design-system
  - theme
  - css
  - components
  - utilities
modules:
  - styles
  - components
code_verified: true
dead_docs_found: false
---

# ScareVerse Design System

Centralized, modular design system for the Cockpit SPA with theme support and minimalist interface.

## Index

### Documentation

- [Theme Guide](./docs/THEME_GUIDE.md) - Complete theme system documentation
- [Theme Utilities](./docs/theme-utilities.md) - Theme-aware CSS utility classes
- [Components Guide](./docs/COMPONENTS.md) - UI components reference
- [Usage Examples](./docs/EXAMPLES.md) - Production-ready code examples

### CSS Files

- `index.css` - Entry point (imports all modules)
- `variables.css` - CSS Custom Properties (theme, colors, spacing)
- `base.css` - Global reset and base styles
- `theme-utilities.css` - **NEW:** Theme-aware utility classes
- `utilities.css` - Utility classes (spacing, flex, text)
- `buttons.css` - Minimalist button system
- `forms.css` - Inputs, selects, checkboxes
- `components.css` - Cards, modals, alerts, badges, etc.

### JavaScript

- `theme.js` - JavaScript API for theme management

## Overview

The ScareVerse Design System follows these principles:

1. **Minimalism**: Clean interface, compact buttons, well-defined spacing
2. **Horizontal First**: Buttons and controls organized horizontally, not vertically
3. **Modularidad**: Small CSS files focused on single responsibilities
4. **Theme Support**: Complete light/dark theme support via CSS variables
5. **Accessibility**: Focus states, proper contrast, semantic HTML

## Quick Start

### Import Styles

```javascript
// In main.js or App.vue
import '@/styles/index.css'
```

### Initialize Theme

```javascript
import { initTheme } from '@/styles/theme.js'

// On app startup
initTheme()
```

### Use Components

```vue
<template>
  <div class="card">
    <div class="card-header">
      <h3 class="card-title">Welcome</h3>
    </div>
    <div class="card-body">
      <p>Start using the design system!</p>
    </div>
    <div class="card-footer">
      <div class="btn-group">
        <button class="btn btn-sm btn-secondary">Cancel</button>
        <button class="btn btn-sm btn-primary">Continue</button>
      </div>
    </div>
  </div>
</template>
```

## File Structure

```
src/styles/
├── docs/                   # Extended documentation
│   ├── THEME_GUIDE.md     # Theme system guide
│   ├── COMPONENTS.md      # Components reference
│   └── EXAMPLES.md        # Usage examples
├── index.css              # Entry point
├── variables.css          # CSS custom properties
├── base.css               # Base styles
├── buttons.css            # Button styles
├── forms.css              # Form styles
├── components.css         # Component styles
├── utilities.css          # Utility classes
├── theme.js               # Theme management
└── README.md              # This file
```

## Key Features

### Theme System

- Light/Dark/Auto themes
- System preference detection
- Persistent user selection
- Smooth transitions
- CSS variables for consistency

See [Theme Guide](./docs/THEME_GUIDE.md) for complete documentation.

### Components

- Buttons (multiple variants and sizes)
- Forms (inputs, selects, validation)
- Cards, alerts, modals
- Badges, spinners, dropdowns
- Tabs, breadcrumbs

See [Components Guide](./docs/COMPONENTS.md) for usage details.

### Utilities

- Spacing (margin, padding)
- Flexbox layout
- Text styling
- Background and borders

## CSS Variables

All theme colors and spacing are defined as CSS custom properties:

```css
/* Colors */
var(--color-primary)
var(--color-text-primary)
var(--color-background)
var(--color-surface)

/* Spacing */
var(--space-xs)  /* 4px */
var(--space-sm)  /* 8px */
var(--space-md)  /* 16px */
var(--space-lg)  /* 24px */

/* Typography */
var(--font-size-sm)   /* 14px */
var(--font-size-base) /* 16px */
var(--font-size-lg)   /* 18px */
```

## Best Practices

### Use the Design System

✅ **Do** use design system classes:

```html
<button class="btn btn-sm btn-primary">Save</button>
```

❌ **Don't** create custom styles:

```html
<button style="background: blue; padding: 10px;">Save</button>
```

### Prefer Horizontal Layouts

✅ **Do** group buttons horizontally:

```html
<div class="btn-group">
  <button class="btn btn-sm">Action 1</button>
  <button class="btn btn-sm">Action 2</button>
</div>
```

❌ **Don't** stack buttons vertically:

```html
<button>Action 1</button><br />
<button>Action 2</button>
```

### Use Theme-Aware Utilities

✅ **Do** use theme utilities for colors that change with theme:

```html
<div class="theme-bg-surface theme-text-primary rounded-lg p-4">
  <h3 class="theme-text-primary">Title</h3>
  <p class="theme-text-secondary">Description</p>
</div>
```

❌ **Don't** use hardcoded Tailwind colors:

```html
<div class="bg-white text-black rounded-lg p-4">
  <h3 class="text-black">Title</h3>
  <p class="text-gray-600">Description</p>
</div>
```

### Use CSS Variables

✅ **Do** use theme variables:

```css
.component {
  color: var(--color-text-primary);
  padding: var(--space-md);
}
```

❌ **Don't** hardcode values:

```css
.component {
  color: #000000;
  padding: 16px;
}
```

## Migration Guide

To migrate existing code to use the design system:

1. **Remove inline styles**: Replace with design system classes
2. **Update buttons**: Use `.btn` with appropriate size/variant
3. **Organize horizontally**: Use `.btn-group` for button groups
4. **Use variables**: Replace fixed values with CSS variables
5. **Apply utilities**: Use spacing, flex, and text utilities

## Testing

Test components in both themes:

- Light theme
- Dark theme
- Check contrast and readability
- Verify all states (hover, active, disabled)

## Performance

The design system is optimized for performance:

- Modular CSS files (load only what you need)
- CSS variables (no runtime JavaScript)
- Minimal file size
- Efficient selectors

## Browser Support

- Chrome/Edge: Latest 2 versions
- Firefox: Latest 2 versions
- Safari: Latest 2 versions
- CSS Variables: All modern browsers

## Related Documentation

- [Frontend Source](../../README.md) - Frontend overview
- [Components Implementation](../../components/) - Component source code
- [Styles Documentation](./docs/) - Extended style guides

## Notes

- Always use design system classes instead of custom styles
- Test components in both light and dark themes
- Keep components modular and reusable
- Follow accessibility best practices
- Technical names use English
- UI text may be in Portuguese

## Support

For questions or issues:

- Check documentation in `docs/` directory
- Review existing components for examples
- See main project documentation

---

**Last Updated**: 2025-11-05  
**Version**: 1.0.0  
**Maintainer**: ScareVerse Team
