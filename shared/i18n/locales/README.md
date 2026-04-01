# Shared i18n Locales

Translation locale files shared across all ScareVerseLab cell types.

## Purpose

This directory contains the base translation dictionaries (`en-US` and `pt-BR`) used by the shared `useCellI18n` composable. Individual cells may extend these base translations with cell-specific keys in their own `translations/` directories.

## Index

### Files

| File | Description |
|------|-------------|
| `en-US.json` | English (United States) translations — the canonical/default locale |
| `pt-BR.json` | Portuguese (Brazil) translations |

## Structure

Both locale files share the same key hierarchy. Common top-level namespaces include:

| Namespace | Contents |
|-----------|----------|
| `common` | Generic UI labels: save, cancel, delete, edit, create, loading, error, success, etc. |
| `actions` | Action button labels and confirmation messages |
| `cells` | Cell-specific labels (title, type, status) |
| `errors` | Error messages and descriptions |
| `validation` | Form validation messages |

## Usage

Locale files are loaded automatically by `useCellI18n` and the shared `useI18nHelper` composable. You do not typically reference these files directly — use the composable instead:

```ts
import { useCellI18n } from '@artifacts/shared/composables/useCellI18n'

const { t } = useCellI18n()
const label = t('common.save') // → "Save" in en-US
```

### Adding new shared keys

1. Add the key to `en-US.json` under the appropriate namespace.
2. Add the translated value to `pt-BR.json` under the same key path.
3. Rebuild or restart the dev server — Vue i18n hot-reloads locale files automatically.

### Cell-specific translations

If a translation key is only relevant to a single cell, add it to that cell's own `translations/` directory rather than here. Cell-specific locales are merged at runtime with these shared ones, with cell-specific keys taking precedence.

## Related Documentation

- [Shared i18n Parent](../) - i18n directory overview
- [Shared Composables](../../composables/) - `useCellI18n` and `useI18nHelper`
- [Shared Artifacts Root](../../) - Overview of all shared artifacts
