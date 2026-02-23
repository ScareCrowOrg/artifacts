/**
 * @file useAIModels.ts
 * @description Composable for AI model configuration management
 * 
 * Provides reactive state and methods for managing AI model providers.
 */

import { ref, computed, type Ref } from 'vue'
import { createLogger } from '@/utils/logger'
import type { AIModelsCell, AIModelProvider, ProviderConfig } from '../AIModelsCell'

const log = createLogger('composables:useAIModels')

/**
 * Provider metadata
 */
export interface ProviderMetadata {
  id: AIModelProvider
  name: string
  icon?: string
  requiresApiKey: boolean
  requiresEndpoint: boolean
  defaultEndpoint?: string
}

/**
 * Provider state
 */
export interface ProviderState {
  config: ProviderConfig
  loading: boolean
  testing: boolean
  connected: boolean | null
  error: string | null
}

/**
 * Available AI model providers
 */
export const AI_MODEL_PROVIDERS: ProviderMetadata[] = [
  {
    id: 'ollama',
    name: 'Ollama',
    requiresApiKey: false,
    requiresEndpoint: true,
    defaultEndpoint: 'http://localhost:11434'
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    requiresApiKey: true,
    requiresEndpoint: false
  },
  {
    id: 'openai',
    name: 'OpenAI',
    requiresApiKey: true,
    requiresEndpoint: false
  }
]

/**
 * Composable for AI models management
 */
export function useAIModels(cellInstance: AIModelsCell) {
  const providers = ref<Record<AIModelProvider, ProviderState>>({
    ollama: {
      config: {},
      loading: false,
      testing: false,
      connected: null,
      error: null
    },
    gemini: {
      config: {},
      loading: false,
      testing: false,
      connected: null,
      error: null
    },
    openai: {
      config: {},
      loading: false,
      testing: false,
      connected: null,
      error: null
    }
  })

  const activeProvider = ref<AIModelProvider>('ollama')

  /**
   * Get current provider state
   */
  const currentProvider = computed(() => providers.value[activeProvider.value])

  /**
   * Get provider metadata by id
   */
  const getProviderMetadata = (providerId: AIModelProvider): ProviderMetadata | undefined => {
    return AI_MODEL_PROVIDERS.find(p => p.id === providerId)
  }

  /**
   * Load configuration for a provider
   */
  const loadProviderConfig = async (providerId: AIModelProvider): Promise<void> => {
    const state = providers.value[providerId]
    state.loading = true
    state.error = null

    try {
      const result = await cellInstance.execute({
        action: 'get',
        provider: providerId
      })

      if (result.success && result.output.config) {
        state.config = result.output.config
        log.debug('Loaded config for provider', { providerId, config: state.config })
      } else {
        throw new Error(result.error || 'Failed to load configuration')
      }
    } catch (error: any) {
      state.error = error.message || 'Failed to load configuration'
      log.error('Error loading provider config', { providerId, error })
    } finally {
      state.loading = false
    }
  }

  /**
   * Load all provider configurations
   */
  const loadAllConfigs = async (): Promise<void> => {
    log.debug('Loading all provider configurations')
    
    const promises = AI_MODEL_PROVIDERS.map(provider => 
      loadProviderConfig(provider.id)
    )

    await Promise.allSettled(promises)
  }

  /**
   * Update configuration for a provider
   */
  const updateProviderConfig = async (
    providerId: AIModelProvider,
    config: ProviderConfig
  ): Promise<boolean> => {
    const state = providers.value[providerId]
    state.loading = true
    state.error = null

    try {
      const result = await cellInstance.execute({
        action: 'update',
        provider: providerId,
        config
      })

      if (result.success) {
        state.config = config
        log.debug('Updated config for provider', { providerId, config })
        return true
      } else {
        throw new Error(result.error || 'Failed to update configuration')
      }
    } catch (error: any) {
      state.error = error.message || 'Failed to update configuration'
      log.error('Error updating provider config', { providerId, error })
      return false
    } finally {
      state.loading = false
    }
  }

  /**
   * Test connection to a provider
   */
  const testProviderConnection = async (
    providerId: AIModelProvider,
    config?: ProviderConfig
  ): Promise<boolean> => {
    const state = providers.value[providerId]
    const testConfig = config || state.config

    state.testing = true
    state.error = null
    state.connected = null

    try {
      const result = await cellInstance.execute({
        action: 'test-connection',
        provider: providerId,
        config: testConfig
      })

      state.connected = result.success && result.output.connected === true
      
      if (!state.connected) {
        state.error = result.error || 'Connection test failed'
      }
      
      log.debug('Connection test result', { 
        providerId, 
        connected: state.connected 
      })

      return state.connected
    } catch (error: any) {
      state.connected = false
      state.error = error.message || 'Connection test failed'
      log.error('Error testing connection', { providerId, error })
      return false
    } finally {
      state.testing = false
    }
  }

  /**
   * Set active provider
   */
  const setActiveProvider = (providerId: AIModelProvider): void => {
    activeProvider.value = providerId
    log.debug('Active provider changed', { providerId })
  }

  /**
   * Reset provider state
   */
  const resetProviderState = (providerId: AIModelProvider): void => {
    const state = providers.value[providerId]
    state.loading = false
    state.testing = false
    state.connected = null
    state.error = null
  }

  /**
   * Validate provider configuration
   */
  const validateProviderConfig = (
    providerId: AIModelProvider,
    config: ProviderConfig
  ): string[] => {
    const errors: string[] = []
    const metadata = getProviderMetadata(providerId)

    if (!metadata) {
      errors.push('Invalid provider')
      return errors
    }

    if (metadata.requiresApiKey && !config.apiKey) {
      errors.push('API key is required')
    }

    if (metadata.requiresEndpoint && !config.endpoint) {
      errors.push('Endpoint URL is required')
    }

    // Validate endpoint URL format for Ollama
    if (providerId === 'ollama' && config.endpoint) {
      try {
        new URL(config.endpoint)
      } catch {
        errors.push('Invalid endpoint URL format')
      }
    }

    return errors
  }

  return {
    // State
    providers,
    activeProvider,
    currentProvider,

    // Metadata
    AI_MODEL_PROVIDERS,
    getProviderMetadata,

    // Actions
    loadProviderConfig,
    loadAllConfigs,
    updateProviderConfig,
    testProviderConnection,
    setActiveProvider,
    resetProviderState,
    validateProviderConfig
  }
}

export type UseAIModelsReturn = ReturnType<typeof useAIModels>
