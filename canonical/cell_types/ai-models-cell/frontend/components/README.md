# AI Models Cell – Frontend Components

## Purpose

Per-provider settings form components for the AI Models Cell. Each component renders the configuration UI for a specific AI provider and emits change events to the parent `View.vue`.

## Content Index

| File | Description |
|------|-------------|
| [`GeminiSettings.vue`](./GeminiSettings.vue) | Configuration form for Google Gemini API — API key, model selection |
| [`OllamaSettings.vue`](./OllamaSettings.vue) | Configuration form for Ollama — host URL, model selection, connection test |
| [`OpenAISettings.vue`](./OpenAISettings.vue) | Configuration form for OpenAI API — API key, model selection, base URL override |

## How to Use

Components are loaded by the parent `View.vue` based on the active provider tab. They receive the current `ProviderConfig` as a prop and emit `update:config` events on change.

## Related

- [`../`](../) — AI Models Cell frontend root
- [`../composables/useAIModels.ts`](../composables/useAIModels.ts) — Composable that manages provider state
