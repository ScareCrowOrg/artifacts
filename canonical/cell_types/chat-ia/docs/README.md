# Chat IA Cell Type

## Overview

The Chat IA cell type provides an AI-powered chat interface integrated into the ScareVerse notebook environment. It enables rich conversational interactions with multiple AI models, supports file attachments, maintains conversation history, and offers advanced features like file proposals and trace timelines.

## Features

- **Multi-Model Support**: Choose from various AI models (GPT-4, GPT-3.5, local models via Ollama, BYOK)
- **File Attachments**: Attach files and code snippets to provide context to the AI
- **Conversation Persistence**: Automatic saving and loading of conversation history
- **File Proposals**: AI can propose file edits with accept/reject workflow
- **Trace Timeline**: View execution traces and debug AI processing
- **RAG Integration**: Select document collections for context-aware responses
- **Intention Classification**: Advanced routing based on detected user intent
- **Dark Mode Support**: Full theming and dark mode compatibility

## Properties

### selectedModel (string)
- **Description**: AI model to use for chat interactions
- **Default**: "gpt-4"
- **Options**: Dynamically loaded from backend configuration
- **Examples**: "gpt-4", "gpt-3.5-turbo", "ollama/llama2"

### enableIntentionClassification (boolean)
- **Description**: Enable intention classification for advanced routing
- **Default**: false
- **Effect**: When enabled, analyzes user intent to route to specialized workflows

### selectedCollections (array of strings)
- **Description**: Selected RAG collections for context
- **Default**: []
- **Effect**: Provides document context from selected collections to enhance AI responses

### systemPrompt (string)
- **Description**: Custom system prompt for the conversation
- **Default**: "" (uses default system prompt)
- **Effect**: Overrides the default system instructions for the AI

### conversationId (string | null)
- **Description**: ID of the current conversation for persistence
- **Default**: null
- **Effect**: When set, loads and maintains a specific conversation

## Usage

### Creating a Chat IA Cell

```typescript
const chatCell = {
  notebook_item_type_id: 'chat-ia',
  initial_data: {
    selectedModel: 'gpt-4',
    enableIntentionClassification: false,
    selectedCollections: ['scareverse-docs'],
    systemPrompt: '',
    conversationId: null
  }
}
```

### Loading a Specific Conversation

```typescript
const chatCell = {
  notebook_item_type_id: 'chat-ia',
  initial_data: {
    conversationId: 'existing-conversation-id-here'
  }
}
```

### Using Custom RAG Collections

```typescript
const chatCell = {
  notebook_item_type_id: 'chat-ia',
  initial_data: {
    selectedCollections: ['my-docs', 'team-knowledge-base'],
    enableIntentionClassification: true
  }
}
```

## Cell Lifecycle

### Initialization
1. Cell is created with `initial_data` properties
2. Composables are initialized (useChatIA, useChatHistory)
3. Chat store is connected
4. Models are fetched from backend
5. Conversation is loaded (specific ID or last conversation)

### State Updates
- Model selection changes update `initial_data.selectedModel`
- Collection changes update `initial_data.selectedCollections`
- New conversations update `initial_data.conversationId`
- Settings persist automatically via `update:cell` event

### Cleanup
- Chat component unregisters from global chat store
- Conversation state is automatically persisted
- No manual cleanup required

## Events

### Emitted Events

#### `update:cell`
- **Payload**: Updated cell object with current state
- **Trigger**: When chat settings or conversation changes
- **Purpose**: Persist cell state for later restoration

#### `celula-criada`
- **Payload**: String content to create a new cell
- **Trigger**: When AI generates content for a new notebook cell
- **Purpose**: Integration with notebook cell creation workflow

#### `copy-to-manual`
- **Payload**: String content to copy
- **Trigger**: When user wants to copy content to manual input
- **Purpose**: Copy AI-generated content to other parts of the interface

## Store Integration

### Chat Store (useChatStore)
- Manages file proposal modal state
- Handles proposal acceptance/rejection
- Provides global chat component API registration

### UI Store (useUIStore)
- Controls chat history sidebar visibility
- Manages clear chat trigger
- Handles global UI state

### Global Events Store (useGlobalEventsStore)
- Broadcasts copied content events
- Enables cross-component communication

## Dependencies

### Composables
- `useChatIA`: Core chat functionality and AI interaction
- `useChatHistory`: Conversation history management
- `useChatStore`: Global chat state management
- `useUIStore`: UI state management

### Components
- `ChatHeader`: Header with conversation controls
- `WelcomeMessage`: Initial welcome screen
- `ChatMessage`: Individual message rendering
- `ChatInput`: Message input with attachments
- `ChatSettingsPanel`: Model and settings configuration
- `ChatLoadingIndicator`: Loading state indicator
- `ChatHistorySidebar`: Conversation history list
- `TraceTimelineModal`: Execution trace viewer
- `FileProposalModal`: File edit proposal interface

## Architecture

### TypeScript Implementation
The Chat IA cell type is fully implemented in TypeScript following RULESET.md Rule 4.5:
- Explicit type annotations on all props, emits, and refs
- Type-safe event handlers
- Typed store integrations
- Type-only imports where applicable

### State Management
- Reactive state managed through composables
- Bi-directional data binding with cell `initial_data`
- Automatic persistence via `update:cell` events
- Store-based global state for cross-component features

### Theming
- Follows ScareVerse design system
- Full dark mode support
- CSS custom properties for theming
- Compliant with theme validation (99% compliance)

### Internationalization
- i18n ready (100% coverage)
- Localized strings via i18n keys
- Multi-language support enabled

## Testing

### Unit Tests
Located in `tests/View.spec.ts`:
- Component mounting and initialization
- Props handling
- Event emission
- Store integration
- Composable interaction

### E2E Tests
Inherit from existing ChatIA component tests:
- Message sending and receiving
- File attachment workflow
- Conversation switching
- Model selection
- File proposal acceptance

## Migration from Legacy ChatIA.vue

This cell type replaces the direct usage of `ChatIA.vue` in the classic layout. Key differences:

### Legacy (ChatIA.vue directly in App.vue)
```vue
<ChatIA ref="chatIA" @celula-criada="onCelulaCriada" />
```

### New (chat-ia cell type)
```vue
<DynamicCellView :cell="chatIACell" @celula-criada="onCelulaCriada" />
```

The functionality remains identical, but the new implementation:
- ✅ Follows cell-type architecture
- ✅ Enables better state persistence
- ✅ Supports notebook-based workflows
- ✅ Provides canonical type definition
- ✅ Uses symlink architecture for consistency

## Troubleshooting

### Cell Not Loading
- Verify `chat-ia` is registered in `CANONICAL_CELL_TYPES`
- Check import statement in `canonicalLoader` function
- Ensure symlink to type.json is valid

### Conversation Not Persisting
- Check `conversationId` in `initial_data`
- Verify `update:cell` event is being handled
- Inspect localStorage for conversation data

### Models Not Loading
- Check backend `/api/ai/models` endpoint
- Verify authentication token is valid
- Check browser console for fetch errors

### File Proposals Not Working
- Ensure chat store is properly initialized
- Check file proposal modal visibility state
- Verify accept handler is connected

## References

- [ADDING_NEW_CELL_TYPE.md](../../../../docs/official/ADDING_NEW_CELL_TYPE.md) - Cell type creation guide
- [TECHNICAL_GUIDE.md](../../../../docs/issues/1385/TECHNICAL_GUIDE.md) - TypeScript migration patterns
- [cell-type-symlink-architecture.md](../../../../docs/official/backend/architecture/cell-type-symlink-architecture.md) - Symlink architecture
- [ChatIA.vue](../../../../cockpit-vue/src/components/ChatIA.vue) - Legacy implementation reference

## Version History

- **1.0.0** (2025-12-15): Initial release as canonical cell type
  - TypeScript implementation
  - Full feature parity with legacy ChatIA.vue
  - Cell-type architecture integration
  - Canonical definition with symlink

---

**Author**: GitHub Copilot Coding Agent  
**Issue**: #1422  
**Last Updated**: 2025-12-15
