# DynamicWorkspace i18n

Internationalization configuration and translation files for the DynamicWorkspace v2 viewer.

## Purpose

This directory provides the standalone `vue-i18n` setup for the DynamicWorkspace viewer:
- Creates an isolated i18n instance (separate from the main Cockpit instance)
- Provides English and Brazilian Portuguese translations for viewer UI strings
- Exports the configured i18n instance for use in `main.ts`

## Directory Structure

```
i18n/
├── index.ts      - vue-i18n instance setup (imports en and pt-BR)
├── en.ts         - English locale type definitions / fallback
├── en.json       - English translation strings
└── pt-BR.json    - Brazilian Portuguese translation strings
```

## How to Use

```typescript
// Imported by main.ts
import i18n from './i18n'
import { createApp } from 'vue'
import App from './App.vue'

const app = createApp(App)
app.use(i18n)
app.mount('#app')
```

```typescript
// In any component or composable
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
console.log(t('workspace.loading'))
```

## Content Index

| File | Description |
|---|---|
| `index.ts` | vue-i18n instance creation (registers en and pt-BR locales) |
| `en.ts` | TypeScript type definitions for English locale keys |
| `en.json` | English translation strings |
| `pt-BR.json` | Brazilian Portuguese translation strings |
