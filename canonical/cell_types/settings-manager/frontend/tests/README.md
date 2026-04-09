# Settings Manager Cell – Frontend Tests

Component tests for the Settings Manager Cell Vue 3 frontend.

## Purpose

Validates the `View.vue` component behavior: rendering the settings list, opening create/edit dialogs, submitting actions to the backend, displaying history, and triggering Redis push.

## Files

| File | Description |
|------|-------------|
| `View.spec.ts` | Vitest + Vue Test Utils tests for the main View.vue component |

## Running Tests

```bash
# From the cell root directory
cd artifacts/canonical/cell_types/settings-manager
npx vitest run frontend/tests/

# Watch mode
npx vitest frontend/tests/
```

## Related Documentation

- [Frontend README](../README.md) — Frontend component overview
- [Cell README](../../README.md) — Cell overview and actions
