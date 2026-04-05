<template>
  <div class="ai-models-panel">
    <header class="panel-header">
      <h2>{{ t('aiModels.title') }}</h2>
      <p class="description">{{ t('aiModels.description') }}</p>
    </header>

    <!-- Provider Tabs -->
    <div class="tabs">
      <button
        v-for="provider in providersList"
        :key="provider.id"
        @click="handleProviderChange(provider.id)"
        :class="['tab-button', { active: activeProviderValue === provider.id }]"
      >
        {{ provider.name }}
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="currentProvider.loading" class="loading-state">
      <span class="spinner"></span>
      <p>{{ t('aiModels.loadingConfig') }}</p>
    </div>

    <!-- Error State -->
    <div v-else-if="currentProvider.error" class="error-state">
      <span class="icon">⚠️</span>
      <p>{{ currentProvider.error }}</p>
      <button @click="retryLoad" class="btn-secondary">
        {{ t('aiModels.retry') }}
      </button>
    </div>

    <!-- Provider Settings -->
    <div v-else class="provider-content">
      <!-- Ollama Settings -->
      <OllamaSettings
        v-if="activeProviderValue === 'ollama'"
        :config="currentProvider.config"
        :testing="currentProvider.testing"
        :connected="currentProvider.connected"
        @update="handleUpdate"
        @test="handleTest"
      />

      <!-- Gemini Settings -->
      <GeminiSettings
        v-else-if="activeProviderValue === 'gemini'"
        :config="currentProvider.config"
        :testing="currentProvider.testing"
        :connected="currentProvider.connected"
        @update="handleUpdate"
        @test="handleTest"
      />

      <!-- OpenAI Settings -->
      <OpenAISettings
        v-else-if="activeProviderValue === 'openai'"
        :config="currentProvider.config"
        :testing="currentProvider.testing"
        :connected="currentProvider.connected"
        @update="handleUpdate"
        @test="handleTest"
      />
    </div>

    <!-- Success Message -->
    <div v-if="successMessage" class="success-toast">
      <span class="icon">✓</span>
      {{ successMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'
import { AIModelsCell } from './AIModelsCell'
import type { AIModelProvider, ProviderConfig } from './AIModelsCell'
import { useAIModels, AI_MODEL_PROVIDERS } from './composables/useAIModels'
import { useAIModelsStore } from './stores/aiModelsStore'
import OllamaSettings from './components/OllamaSettings.vue'
import GeminiSettings from './components/GeminiSettings.vue'
import OpenAISettings from './components/OpenAISettings.vue'

const log = createLogger('cells:AIModels:View')
const { t } = useI18n()

// Props
interface Props {
  cellInstance: AIModelsCell
}

const props = defineProps<Props>()

// State
const store = useAIModelsStore()
const {
  providers,
  activeProvider,
  currentProvider,
  loadAllConfigs,
  updateProviderConfig,
  testProviderConnection,
  setActiveProvider
} = useAIModels(props.cellInstance)

const successMessage = ref('')
const providersList = AI_MODEL_PROVIDERS
const activeProviderValue = computed(() => activeProvider.value)

/**
 * Handle provider tab change
 */
const handleProviderChange = (providerId: AIModelProvider) => {
  setActiveProvider(providerId)
  store.setActiveProvider(providerId)
}

/**
 * Handle configuration update
 */
const handleUpdate = async (config: ProviderConfig) => {
  const providerId = activeProvider.value
  
  log.debug('Updating configuration', { providerId, config })
  
  const success = await updateProviderConfig(providerId, config)
  
  if (success) {
    store.setConfig(providerId, config)
    store.saveConfigsToStorage()
    showSuccess(t('aiModels.configSaved'))
  }
}

/**
 * Handle connection test
 */
const handleTest = async (config?: ProviderConfig) => {
  const providerId = activeProvider.value
  
  log.debug('Testing connection', { providerId })
  
  const connected = await testProviderConnection(providerId, config)
  
  if (connected) {
    showSuccess(t('aiModels.connectionSuccess'))
  }
}

/**
 * Retry loading configuration
 */
const retryLoad = async () => {
  await loadAllConfigs()
}

/**
 * Show success message
 */
const showSuccess = (message: string) => {
  successMessage.value = message
  setTimeout(() => {
    successMessage.value = ''
  }, 3000)
}

/**
 * Initialize
 */
onMounted(async () => {
  log.debug('AI Models View mounted')
  
  // Load stored configs first
  store.loadConfigsFromStorage()
  
  // Then load from backend
  await loadAllConfigs()
  
  // Sync store with loaded configs
  Object.entries(providers.value).forEach(([providerId, state]) => {
    if (state.config && Object.keys(state.config).length > 0) {
      store.setConfig(providerId as AIModelProvider, state.config)
    }
  })
})

// Watch for store changes and save to localStorage
watch(
  () => store.configs,
  () => {
    store.saveConfigsToStorage()
  },
  { deep: true }
)
</script>

<style scoped>
.ai-models-panel {
  padding: var(--space-lg);
  max-width: 1200px;
  margin: 0 auto;
}

.panel-header {
  margin-bottom: var(--space-xl);
}

.panel-header h2 {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-sm);
}

.panel-header .description {
  font-size: var(--font-size-md);
  color: var(--color-text-secondary);
}

.tabs {
  display: flex;
  gap: var(--space-sm);
  margin-bottom: var(--space-xl);
  border-bottom: 2px solid var(--color-border);
}

.tab-button {
  padding: var(--space-md) var(--space-lg);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: -2px;
}

.tab-button:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
}

.tab-button.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-2xl);
  gap: var(--space-md);
}

.loading-state .spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-state {
  color: var(--color-error);
}

.error-state .icon {
  font-size: var(--font-size-3xl);
}

.provider-content {
  background: var(--color-bg-secondary);
  border-radius: var(--radius-lg);
  padding: var(--space-xl);
}

.success-toast {
  position: fixed;
  top: var(--space-lg);
  right: var(--space-lg);
  background: var(--color-success);
  color: white;
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  z-index: var(--z-modal);
  animation: slideIn 0.3s ease-out;
}

.success-toast .icon {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.btn-secondary {
  padding: var(--space-sm) var(--space-md);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-secondary:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-primary);
}
</style>
