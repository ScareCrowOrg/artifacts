---
processed: true
processed_date: 2025-12-10
themes:
  - frontend
  - i18n
  - localization
modules:
  - cockpit-vue
code_verified: true
dead_docs_found: false
note: Source-level documentation, stays with code
---

# Internationalization (I18n) Guide

This directory contains the internationalization (i18n) configuration and locale files for the ScareVerse frontend.

## Overview

The ScareVerse frontend uses **vue-i18n** to provide internationalization support:
- **Technical code** (variables, functions, class names, attributes) remains in **English**
- **User-facing strings** (UI labels, messages, errors) are **localized** via i18n

## Supported Locales

| Locale Code | Language | Status | Default |
|-------------|----------|--------|---------|
| `pt-BR` | Português (Brasil) | ✅ Complete | ✅ Yes |
| `en-US` | English (US) | ✅ Complete | No |

## Directory Structure

```
src/i18n/
├── index.js              # I18n configuration and setup
├── locales/
│   ├── pt-BR.json       # Portuguese translations
│   └── en-US.json       # English translations
└── README.md            # This file
```

## Usage

### In Vue Templates

Use the global `$t()` function:

```vue
<template>
  <div>
    <h1>{{ $t('cells.title') }}</h1>
    <button>{{ $t('common.save') }}</button>
    <p class="error">{{ $t('errors.cellNotFound') }}</p>
  </div>
</template>
```

### In Script Setup

Use the `useI18nHelper` composable:

```vue
<script setup>
import { useI18nHelper } from '@/composables/useI18nHelper'

const { t, tp, getErrorMessage } = useI18nHelper()

// Simple translation
const title = t('cells.title')

// Translation with parameters
const message = tp('messages.createSuccess', { entity: 'Cell' })

// Error handling from backend
const error = getErrorMessage({ 
  i18n_key: 'errors.cellNotFound',
  details: { cell_id: 'abc123' }
})
</script>
```

### Change Locale

```vue
<script setup>
import { useI18nHelper } from '@/composables/useI18nHelper'

const { changeLocale, availableLocales } = useI18nHelper()

// Change to English
changeLocale('en-US')

// Change to Portuguese
changeLocale('pt-BR')
</script>
```

## Available Translation Keys

### Common Actions
- `common.save` - Save
- `common.cancel` - Cancel
- `common.delete` - Delete
- `common.edit` - Edit
- `common.create` - Create
- `common.loading` - Loading...
- `common.error` - Error
- `common.success` - Success

### Cells
- `cells.title` - Cells
- `cells.create` - Create Cell
- `cells.edit` - Edit Cell
- `cells.delete` - Delete Cell
- `cells.status` - Status
- `cells.fragments` - Fragments
- `cells.assignee` - Assignee

### Books
- `books.title` - Books
- `books.create` - Create Book
- `books.purpose` - Purpose
- `books.type` - Type
- `books.children` - Children

### Fragments
- `fragments.title` - Fragments
- `fragments.content` - Content
- `fragments.add` - Add Fragment

### Errors
- `errors.generic` - Generic error
- `errors.cellNotFound` - Cell not found
- `errors.bookNotFound` - Book not found
- `errors.saveFailed` - Save failed
- `errors.loadFailed` - Load failed
- `errors.invalidData` - Invalid data
- `errors.networkError` - Network error

### Status
- `status.pending` - Pending
- `status.running` - Running
- `status.completed` - Completed
- `status.error` - Error

### Messages
- `messages.createSuccess` - Created successfully (with parameter)
- `messages.updateSuccess` - Updated successfully (with parameter)
- `messages.deleteSuccess` - Deleted successfully (with parameter)

## Adding New Translations

### 1. Add to Both Locale Files

**pt-BR.json:**
```json
{
  "myFeature": {
    "title": "Minha Funcionalidade",
    "description": "Descrição da funcionalidade"
  }
}
```

**en-US.json:**
```json
{
  "myFeature": {
    "title": "My Feature",
    "description": "Feature description"
  }
}
```

### 2. Use in Components

```vue
<template>
  <h1>{{ $t('myFeature.title') }}</h1>
  <p>{{ $t('myFeature.description') }}</p>
</template>
```

## Backend Integration

The backend API returns error responses with `i18n_key` for localization:

```json
{
  "detail": {
    "message": "Cell not found: abc123",
    "i18n_key": "errors.cellNotFound",
    "details": {
      "cell_id": "abc123"
    }
  }
}
```

Use `getErrorMessage()` to handle these errors:

```javascript
try {
  await api.createCell(data)
} catch (error) {
  const message = getErrorMessage(error.response.data.detail)
  // Display localized message to user
  showNotification(message)
}
```

## Best Practices

### DO ✅
- Keep all technical names (variables, functions, classes) in English
- Localize all user-facing strings (labels, messages, errors)
- Use descriptive translation keys (e.g., `cells.create` not `c1`)
- Group related translations by feature (e.g., `cells.*`, `books.*`)
- Add both pt-BR and en-US translations when adding new keys
- Use parameters for dynamic content: `$t('messages.createSuccess', { entity: 'Cell' })`

### DON'T ❌
- Don't hardcode user-facing strings in templates or scripts
- Don't translate technical terms (e.g., "Cell" model name stays "Cell" in code)
- Don't create deeply nested translation keys (max 3 levels)
- Don't add locale-specific keys without adding to all locales
- Don't use translation keys for technical identifiers

## Locale Preference

User's locale preference is automatically:
1. Loaded from `localStorage` if previously set
2. Detected from browser language (`navigator.language`)
3. Defaults to `pt-BR` if neither is available

The preference is saved to `localStorage` when changed via `changeLocale()`.

## Technical Details

### Configuration

The i18n instance is configured in `src/i18n/index.js`:
- **Legacy mode:** Disabled (using Composition API mode)
- **Default locale:** `pt-BR`
- **Fallback locale:** `en-US`
- **Global injection:** Enabled (allows `$t()` in templates)

### Composable Helper

The `useI18nHelper` composable (`src/composables/useI18nHelper.js`) provides:
- `t(key)` - Translate a key
- `tp(key, params)` - Translate with parameters
- `te(entity)` - Translate entity name
- `locale` - Current locale (reactive)
- `availableLocales` - List of available locales
- `changeLocale(code)` - Change current locale
- `getErrorMessage(error)` - Get localized error message

## Migration from Hardcoded Strings

When migrating existing components to use i18n:

1. **Identify hardcoded strings:**
   ```vue
   <!-- Before -->
   <button>Salvar</button>
   ```

2. **Add translation keys:**
   ```json
   // pt-BR.json
   { "common": { "save": "Salvar" } }
   
   // en-US.json
   { "common": { "save": "Save" } }
   ```

3. **Update component:**
   ```vue
   <!-- After -->
   <button>{{ $t('common.save') }}</button>
   ```

## Testing

Test that translations work correctly:

```javascript
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import MyComponent from './MyComponent.vue'

const i18n = createI18n({
  locale: 'en-US',
  messages: {
    'en-US': { cells: { title: 'Cells' } }
  }
})

test('displays translated title', () => {
  const wrapper = mount(MyComponent, {
    global: { plugins: [i18n] }
  })
  expect(wrapper.text()).toContain('Cells')
})
```

## Resources

- [vue-i18n Documentation](https://vue-i18n.intlify.dev/)
- [ScareVerse Migration Guide](../../docs/migrations/FINAL_REFACTOR_MIGRATION_GUIDE.md)
- [useI18nHelper Composable](../composables/useI18nHelper.js)

---

**Last Updated:** 2025-12-02  
**Version:** 1.0.0
