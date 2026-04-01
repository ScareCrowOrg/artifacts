# Example Cell — Frontend

Vue 3 frontend for the Example Cell, providing a minimal reference implementation of the cell frontend pattern.

## Purpose

This package demonstrates the canonical frontend structure for a ScareVerse cell. It is the **starting point** for developers creating new cell types. Copy this directory, rename it, and replace the placeholder content in `View.vue` with your cell's actual UI.

## Index

### Files

| File | Description |
|------|-------------|
| `View.vue` | Root Vue component — renders a simple input field and output display as a demonstration |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `tests/` | `View.spec.js` — component test demonstrating the test pattern for cell frontends |
| `translations/` | i18n locale files: `en.json`, `pt-BR.json` — minimal translation keys as a starting template |

## Overview

`View.vue` demonstrates:
- How to receive `cell` props from the cockpit-vue shell
- How to call `execute-ephemeral` via a shared service composable
- How to display execution output
- How to use i18n translation keys

## How to Use as a Template

1. Copy the `example/` directory: `cp -r example/ my-new-cell/`
2. Rename the cell class in `View.vue`
3. Replace the UI with your cell's interface
4. Update translation keys in `translations/en.json` and `translations/pt-BR.json`
5. Add your specific tests in `tests/View.spec.js`
6. Register the cell type by creating/updating `type.json` at the cell root

## Running Tests

```bash
npx vitest run artifacts/canonical/cell_types/example/frontend/tests/
```

## Related Documentation

- [Example Cell Root](../) - Full cell overview and template guidance
- [Example Cell Backend](../backend/) - Python execution backend template
- [Shared Composables](../../../../shared/composables/) - Available composables to use in your cell
- [Shared i18n Locales](../../../../shared/i18n/locales/) - Base translations to extend
- [Adding New Cell Type](../../../../../docs/official/ADDING_NEW_CELL_TYPE.md) - Official guide
