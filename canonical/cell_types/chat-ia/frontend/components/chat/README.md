# Chat IA Cell – Chat Interaction Components

## Purpose

Core chat interaction Vue 3 components for the **Chat IA Cell**. These components handle the main chat UI: message display, input, settings panels, conversation tracing, and agent terminal.

## Content Index

| File | Description |
|------|-------------|
| [`AgentTerminal.vue`](./AgentTerminal.vue) | Terminal output panel for agent-mode execution — shows tool calls, outputs, status |
| [`ChatHeader.vue`](./ChatHeader.vue) | Chat panel header — model selector, history toggle, settings button |
| [`ChatInput.vue`](./ChatInput.vue) | Message input area — text input, file attachment, send button, voice input |
| [`ChatLoadingIndicator.vue`](./ChatLoadingIndicator.vue) | Animated loading/thinking indicator displayed while AI responds |
| [`ChatMessage.vue`](./ChatMessage.vue) | Renders a single chat message (user or assistant) with Markdown and action links |
| [`ChatSettingsModal.vue`](./ChatSettingsModal.vue) | Modal dialog for chat settings — system prompt, context window, temperature |
| [`ChatSettingsPanel.vue`](./ChatSettingsPanel.vue) | Inline settings panel (alternative to modal for larger screens) |
| [`CollectionSelector.vue`](./CollectionSelector.vue) | Dropdown to select a document collection for RAG context |
| [`ContextBar.vue`](./ContextBar.vue) | Displays active context items (attached files, selected collection) |
| [`DiffViewer.vue`](./DiffViewer.vue) | Side-by-side diff display for file proposals from the AI |
| [`FileProposalModal.vue`](./FileProposalModal.vue) | Modal to review and accept/reject AI-proposed file changes |
| [`TraceFragmentItem.vue`](./TraceFragmentItem.vue) | Renders a single trace fragment in the timeline |
| [`TraceTimelineButton.vue`](./TraceTimelineButton.vue) | Button to toggle the conversation trace timeline overlay |
| [`TraceTimelineModal.vue`](./TraceTimelineModal.vue) | Full trace timeline modal — shows tool calls, agent reasoning, timings |
| [`WelcomeMessage.vue`](./WelcomeMessage.vue) | Initial welcome screen shown when chat history is empty |

## Related

- [`../`](../) — Chat IA Cell frontend components root
- [`../../composables/`](../../composables/) — Composables used by these components
- [`../../stores/`](../../stores/) — Pinia stores for chat and UI state
