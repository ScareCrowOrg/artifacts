/**
 * @file aiModelsStore.ts
 * @description Pinia store for AI models configuration state management
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { createLogger } from '@/utils/logger'
import type { AIModelProvider, ProviderConfig } from '../AIModelsCell'

const log = createLogger('stores:aiModels')

/**
 * AI Models configuration store
 */
export const useAIModelsStore = defineStore('aiModels', () => {
  // State
  const configs = ref<Record<AIModelProvider, ProviderConfig>>({
    ollama: {},
    gemini: {},
    openai: {}
  })

  const activeProvider = ref<AIModelProvider>('ollama')
  const lastUpdated = ref<Record<AIModelProvider, string>>({
    ollama: '',
    gemini: '',
    openai: ''
  })

  // Getters
  const getConfig = computed(() => {
    return (provider: AIModelProvider) => configs.value[provider] || {}
  })

  const currentConfig = computed(() => {
    return configs.value[activeProvider.value] || {}
  })

  const hasValidConfig = computed(() => {
    return (provider: AIModelProvider) => {
      const config = configs.value[provider]
      
      switch (provider) {
        case 'ollama':
          return !!config.endpoint
        case 'gemini':
        case 'openai':
          return !!config.apiKey
        default:
          return false
      }
    }
  })

  // Actions
  const setConfig = (provider: AIModelProvider, config: ProviderConfig) => {
    configs.value[provider] = config
    lastUpdated.value[provider] = new Date().toISOString()
    log.debug('Config updated', { provider, config })
  }

  const updateConfig = (provider: AIModelProvider, updates: Partial<ProviderConfig>) => {
    configs.value[provider] = {
      ...configs.value[provider],
      ...updates
    }
    lastUpdated.value[provider] = new Date().toISOString()
    log.debug('Config partially updated', { provider, updates })
  }

  const clearConfig = (provider: AIModelProvider) => {
    configs.value[provider] = {}
    lastUpdated.value[provider] = ''
    log.debug('Config cleared', { provider })
  }

  const setActiveProvider = (provider: AIModelProvider) => {
    activeProvider.value = provider
    log.debug('Active provider changed', { provider })
  }

  const loadConfigsFromStorage = () => {
    try {
      const stored = localStorage.getItem('ai-models-configs')
      if (stored) {
        const parsed = JSON.parse(stored)
        configs.value = parsed.configs || configs.value
        lastUpdated.value = parsed.lastUpdated || lastUpdated.value
        log.debug('Configs loaded from storage')
      }
    } catch (error) {
      log.error('Error loading configs from storage', error)
    }
  }

  const saveConfigsToStorage = () => {
    try {
      const data = {
        configs: configs.value,
        lastUpdated: lastUpdated.value
      }
      localStorage.setItem('ai-models-configs', JSON.stringify(data))
      log.debug('Configs saved to storage')
    } catch (error) {
      log.error('Error saving configs to storage', error)
    }
  }

  return {
    // State
    configs,
    activeProvider,
    lastUpdated,

    // Getters
    getConfig,
    currentConfig,
    hasValidConfig,

    // Actions
    setConfig,
    updateConfig,
    clearConfig,
    setActiveProvider,
    loadConfigsFromStorage,
    saveConfigsToStorage
  }
})
