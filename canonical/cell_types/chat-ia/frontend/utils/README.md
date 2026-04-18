# Chat IA Cell – Utilities

## Purpose

Utility functions for the Chat IA Cell frontend.

## Content Index

| File | Description |
|------|-------------|
| [`actionLinksPlugin.ts`](./actionLinksPlugin.ts) | Markdown-It plugin for Action Links — detects `json` code blocks with `action` key and renders them as interactive buttons; unified system for tool-call UI |

## How to Use

```typescript
import { actionLinksPlugin } from './utils/actionLinksPlugin'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt()
md.use(actionLinksPlugin, { onAction: handleAction })
```

## Related

- [`../`](../) — Chat IA Cell frontend root
- [`../components/ActionLink.vue`](../components/ActionLink.vue) — Component rendered by this plugin
