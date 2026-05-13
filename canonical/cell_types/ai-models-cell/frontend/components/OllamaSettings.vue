/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="ollama-settings">
    <h3>{{ t('aiModels.providers.ollama.title') }}</h3>
    <p class="description">{{ t('aiModels.providers.ollama.description') }}</p>

    <form @submit.prevent="handleSave" class="settings-form">
      <!-- Endpoint -->
      <div class="form-group">
        <label for="ollama-endpoint">
          {{ t('aiModels.providers.ollama.endpoint') }}
          <span class="required">*</span>
        </label>
        <input
          id="ollama-endpoint"
          v-model="localConfig.endpoint"
          type="text"
          :placeholder="t('aiModels.providers.ollama.endpointPlaceholder')"
          required
        />
        <small class="hint">{{ t('aiModels.providers.ollama.endpointHint') }}</small>
      </div>

      <!-- Model Name -->
      <div class="form-group">
        <label for="ollama-model">
          {{ t('aiModels.providers.ollama.modelName') }}
        </label>
        <input
          id="ollama-model"
          v-model="localConfig.modelName"
          type="text"
          :placeholder="t('aiModels.providers.ollama.modelPlaceholder')"
        />
        <small class="hint">{{ t('aiModels.providers.ollama.modelHint') }}</small>
      </div>

      <!-- Connection Status -->
      <div v-if="connected !== null" class="connection-status" :class="{ success: connected, error: !connected }">
        <span class="icon">{{ connected ? '✓' : '✗' }}</span>
        <span>{{ connected ? t('aiModels.connected') : t('aiModels.disconnected') }}</span>
      </div>

      <!-- Actions -->
      <div class="actions">
        <button
          type="button"
          @click="handleTest"
          :disabled="testing || !localConfig.endpoint"
          class="btn-secondary"
        >
          <span v-if="testing" class="spinner-small"></span>
          {{ testing ? t('aiModels.testing') : t('aiModels.testConnection') }}
        </button>

        <button
          type="submit"
          :disabled="!hasChanges || !localConfig.endpoint"
          class="btn-primary"
        >
          {{ t('aiModels.save') }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProviderConfig } from '../AIModelsCell'

const { t } = useI18n()

interface Props {
  config: ProviderConfig
  testing: boolean
  connected: boolean | null
}

interface Emits {
  (e: 'update', config: ProviderConfig): void
  (e: 'test', config: ProviderConfig): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Local config state
const localConfig = ref<ProviderConfig>({
  endpoint: props.config.endpoint || 'http://localhost:11434',
  modelName: props.config.modelName || 'llama2'
})

// Check if config has changes
const hasChanges = computed(() => {
  return (
    localConfig.value.endpoint !== props.config.endpoint ||
    localConfig.value.modelName !== props.config.modelName
  )
})

// Watch for external config changes
watch(
  () => props.config,
  (newConfig) => {
    if (newConfig.endpoint) {
      localConfig.value.endpoint = newConfig.endpoint
    }
    if (newConfig.modelName) {
      localConfig.value.modelName = newConfig.modelName
    }
  },
  { deep: true }
)

/**
 * Handle save
 */
const handleSave = () => {
  emit('update', { ...localConfig.value })
}

/**
 * Handle test connection
 */
const handleTest = () => {
  emit('test', { ...localConfig.value })
}
</script>

<style scoped>
.ollama-settings {
  max-width: 600px;
}

.ollama-settings h3 {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-sm);
}

.description {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-xl);
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.form-group label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.form-group label .required {
  color: var(--color-error);
}

.form-group input {
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-md);
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  transition: border-color 0.2s ease;
}

.form-group input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.connection-status {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}

.connection-status.success {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.connection-status.error {
  background: var(--color-error-bg);
  color: var(--color-error);
}

.actions {
  display: flex;
  gap: var(--space-md);
  margin-top: var(--space-md);
}

.btn-primary,
.btn-secondary {
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-md);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  display: flex;
  align-items: center;
  gap: var(--space-xs);
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-dark);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-bg-hover);
  border-color: var(--color-primary);
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner-small {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
