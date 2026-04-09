# Settings Manager Cell – Frontend Translations

i18n translation files for the Settings Manager Cell.

## Purpose

Contains English translation strings used by `View.vue` via Vue i18n. All user-visible text in the component is externalized here under the `settingsManager` namespace.

## Files

| File | Description |
|------|-------------|
| `en.json` | English translations for all Settings Manager UI strings |

## Adding a New Language

1. Copy `en.json` to `{locale}.json` (e.g., `pt.json` for Portuguese).
2. Translate the values while keeping all keys identical.
3. Register the new locale in the cockpit-vue i18n configuration.

## Namespace

All keys are nested under `settingsManager`:

```json
{
  "settingsManager": {
    "title": "Settings Manager",
    "description": "...",
    "actions": { ... },
    ...
  }
}
```

## Related Documentation

- [Frontend README](../README.md) — Frontend component overview
- [Cell README](../../README.md) — Cell overview
