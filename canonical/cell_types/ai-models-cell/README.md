# AI Models Cell

Administrative cell for managing AI model configurations across multiple providers.

## Overview

The AI Models Cell provides a secure, RBAC-protected interface for configuring AI model providers (Ollama, Gemini, OpenAI) used throughout the ScareVerse system. Only users with `ai-models:admin` permission can access and modify configurations.

## Features

- **RBAC Protected**: Requires `ai-models:admin` permission
- **Multi-Provider Support**: Ollama, Google Gemini, OpenAI
- **Configuration Management**: Get, update, and test provider configurations
- **Connection Testing**: Validate API keys and endpoints before saving
- **Secure Storage**: API keys are stored securely and never logged
- **Persistent State**: Configurations are persisted to backend and localStorage

## Directory Structure

```
ai-models-cell/
├── type.json                          # Cell metadata (symlink)
├── frontend/
│   ├── AIModelsCell.ts                # BaseCell implementation
│   ├── View.vue                       # Main UI container
│   ├── components/
│   │   ├── OllamaSettings.vue         # Ollama configuration UI
│   │   ├── GeminiSettings.vue         # Gemini configuration UI
│   │   └── OpenAISettings.vue         # OpenAI configuration UI
│   ├── composables/
│   │   └── useAIModels.ts             # AI models composable
│   ├── stores/
│   │   └── aiModelsStore.ts           # Pinia store
│   └── tests/
│       └── [test files]
├── backend/
│   └── [backend scripts if needed]
└── README.md                          # This file
```

## Usage

### As a Cell (Headless)

```typescript
import { AIModelsCell } from '@/artifacts/canonical/cell_types/ai-models-cell/frontend/AIModelsCell'

const cell = new AIModelsCell()

// Get configuration for a provider
const result = await cell.execute({
  action: 'get',
  provider: 'ollama'
})

// Update configuration
const updateResult = await cell.execute({
  action: 'update',
  provider: 'ollama',
  config: {
    endpoint: 'http://localhost:11434',
    modelName: 'llama2'
  }
})

// Test connection
const testResult = await cell.execute({
  action: 'test-connection',
  provider: 'gemini',
  config: {
    apiKey: 'your-api-key',
    modelName: 'gemini-pro'
  }
})
```

### As a UI Component

The cell automatically renders its View.vue component when instantiated in a notebook or workspace.

```typescript
// The cell is auto-discovered and can be added to notebooks
// Users with ai-models:admin permission can access the configuration UI
```

## Actions

### `get`
Retrieve current configuration for a provider.

**Input:**
```typescript
{
  action: 'get',
  provider?: 'ollama' | 'gemini' | 'openai' // Optional, omit to get all
}
```

**Output:**
```typescript
{
  success: true,
  output: {
    action: 'get',
    provider: 'ollama',
    config: {
      endpoint: 'http://localhost:11434',
      modelName: 'llama2'
    }
  }
}
```

### `update`
Update configuration for a provider.

**Input:**
```typescript
{
  action: 'update',
  provider: 'ollama' | 'gemini' | 'openai',
  config: {
    endpoint?: string,      // For Ollama
    apiKey?: string,        // For Gemini, OpenAI
    modelName?: string,     // For all providers
    organizationId?: string // For OpenAI (optional)
  }
}
```

**Output:**
```typescript
{
  success: true,
  output: {
    action: 'update',
    provider: 'ollama',
    config: { /* updated config */ }
  }
}
```

### `test-connection`
Test connection to a provider with given configuration.

**Input:**
```typescript
{
  action: 'test-connection',
  provider: 'ollama' | 'gemini' | 'openai',
  config: {
    endpoint?: string,
    apiKey?: string,
    modelName?: string
  }
}
```

**Output:**
```typescript
{
  success: true, // true if connected, false otherwise
  output: {
    action: 'test-connection',
    provider: 'ollama',
    connected: true
  }
}
```

## Providers

### Ollama
- **Requires**: Endpoint URL (e.g., `http://localhost:11434`)
- **Optional**: Model name (e.g., `llama2`, `mistral`)
- **Connection Test**: Validates endpoint accessibility

### Google Gemini
- **Requires**: API key
- **Optional**: Model name (default: `gemini-pro`)
- **Models**: `gemini-pro`, `gemini-pro-vision`, `gemini-ultra`
- **Connection Test**: Validates API key with Google AI API

### OpenAI
- **Requires**: API key
- **Optional**: Model name (default: `gpt-4`), Organization ID
- **Models**: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`, `gpt-4o`
- **Connection Test**: Validates API key with OpenAI API

## Security

### RBAC
- **Permission Required**: `ai-models:admin`
- **Enforcement**: Every `execute()` call checks permission first
- **Rejection**: Returns error if user lacks permission

### API Key Storage
- API keys are **never logged** to console or files
- Stored securely in backend database with encryption
- Frontend uses masked input fields for API keys
- localStorage cache is optional and can be disabled

### Best Practices
1. Only grant `ai-models:admin` to trusted administrators
2. Rotate API keys regularly
3. Use environment variables for default/fallback configurations
4. Test connections before saving to avoid invalid configurations

## Testing

Run tests with:

```bash
npm run test -- ai-models-cell
```

### Test Coverage
- Unit tests for AIModelsCell
- RBAC permission enforcement tests
- Provider configuration validation tests
- Component tests for UI elements
- Integration tests for API interactions

**Target Coverage**: 85%+

## API Endpoints

The cell uses the following backend endpoints:

- `GET /api/ai-models/config` - Get all configurations
- `GET /api/ai-models/config/:provider` - Get provider config
- `PUT /api/ai-models/config/:provider` - Update provider config
- `POST /api/ai-models/test-connection/:provider` - Test connection
- `GET /api/ai-models/health` - Health check

## Dependencies

- `@/types/BaseCell` - BaseCell interface
- `@/services/apiService` - API client with auth
- `@/stores/auth` - Authentication store
- `@/composables/usePermissions` - RBAC permissions
- `@/utils/logger` - Structured logging
- `vue-i18n` - Internationalization
- `pinia` - State management

## Version History

- **1.0.0** - Initial implementation with Ollama, Gemini, OpenAI support

## Related Documentation

- [ADDING_NEW_CELL_TYPE.md](../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [BaseCell Interface](../../../cockpit-vue/src/types/BaseCell.ts)
- [RBAC Documentation](../../../docs/official/RBAC.md)

## Maintainers

This cell is part of the ScareVerse project and follows AI-driven development practices.

## License

Part of the ScareVerse ecosystem.
