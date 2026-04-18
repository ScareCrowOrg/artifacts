# Chat IA Cell – Frontend Components

## Purpose

Vue 3 components for the **Chat IA Cell** frontend. Organized into top-level utility components and a `chat/` subdirectory for the core chat interaction UI.

## Content Index

### Top-Level Components

| File | Description |
|------|-------------|
| [`ActionLink.vue`](./ActionLink.vue) | Renders an action link button — triggers cell actions from chat context |
| [`ChatHistorySidebar.vue`](./ChatHistorySidebar.vue) | Collapsible sidebar showing conversation history list |
| [`MarkdownRenderer.vue`](./MarkdownRenderer.vue) | Renders Markdown-formatted chat messages with syntax highlighting and diff support |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`chat/`](./chat/) | Core chat interaction components (messages, input, settings, trace timeline, etc.) |

## Related

- [`./chat/`](./chat/) — 11 chat-specific components
- [`../`](../) — Chat IA Cell frontend root
- [`../composables/useChatIA.ts`](../composables/useChatIA.ts) — Primary composable used by these components
