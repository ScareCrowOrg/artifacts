# Chat IA Cell — Frontend

Vue 3 frontend for the Chat IA cell, providing an interactive AI chat interface within the ScareVerse Cockpit.

## Purpose

This package contains the complete frontend implementation of the Chat IA cell: the main view, sub-components, composables, services, stores, translations, and type definitions.

## Index

### Files

| File | Description |
|------|-------------|
| `ChatCell.ts` | TypeScript class implementing `BaseCell` for the Chat IA cell — handles initialization, execution dispatch, and lifecycle |
| `View.vue` | Root Vue component for the cell — mounts the chat interface and wires composables |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `components/` | Chat UI components: `ActionLink.vue`, `ChatHistorySidebar.vue`, `MarkdownRenderer.vue`, `chat/` (message list, input bar) |
| `composables/` | `useActionDiscovery.ts`, `useChatHistory.ts`, `useChatIA.ts`, `useConversationTrace.ts` |
| `config/` | Chat-specific configuration (model defaults, limits) |
| `services/` | `aiChatService.ts` (LLM API calls), `tracesService.ts` (conversation tracing) |
| `stores/` | Pinia stores: `chat.ts` (messages, session), `ui.ts` (panel state) |
| `tests/` | Vitest unit and component tests |
| `translations/` | i18n locale files: `en.json`, `pt-BR.json` |
| `types/` | TypeScript type definitions: `chat.ts` (message, session, response shapes) |
| `utils/` | `actionLinksPlugin.ts` — Vue plugin that registers action link directives |

## Key Components

### `View.vue`

Entry point rendered by the cell host. Composes `useChatIA` for message management and `useActionDiscovery` for detecting executable actions in AI responses.

### `useChatIA.ts`

Primary composable managing:
- Message history (send, receive, stream)
- Session management
- Cancellation of in-flight requests

### `MarkdownRenderer.vue`

Renders AI responses as formatted Markdown with syntax highlighting and action link support.

## Usage

The frontend is loaded dynamically by the cockpit-vue shell when a Chat IA cell is activated. It communicates with the backend via `aiChatService.ts`.

## Related Documentation

- [Chat IA Cell Root](../) - Full cell overview including backend
- [Chat IA Backend](../backend/) - Python execution backend
- [Shared Composables](../../../../shared/composables/) - Platform-wide composables
- [Shared i18n Locales](../../../../shared/i18n/locales/) - Base translations extended here
