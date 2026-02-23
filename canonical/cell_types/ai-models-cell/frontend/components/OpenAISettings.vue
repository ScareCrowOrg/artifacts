<template>
  <div class="openai-settings">
    <h3>{{ t('aiModels.providers.openai.title') }}</h3>
    <p class="description">{{ t('aiModels.providers.openai.description') }}</p>

    <form @submit.prevent="handleSave" class="settings-form">
      <!-- API Key -->
      <div class="form-group">
        <label for="openai-api-key">
          {{ t('aiModels.providers.openai.apiKey') }}
          <span class="required">*</span>
        </label>
        <div class="input-with-toggle">
          <input
            id="openai-api-key"
            v-model="localConfig.apiKey"
            :type="showApiKey ? 'text' : 'password'"
            :placeholder="t('aiModels.providers.openai.apiKeyPlaceholder')"
            required
          />
          <button
            type="button"
            @click="showApiKey = !showApiKey"
            class="toggle-visibility"
            :aria-label="showApiKey ? t('aiModels.hide') : t('aiModels.show')"
          >
            {{ showApiKey ? '👁️' : '👁️‍🗨️' }}
          </button>
        </div>
        <small class="hint">{{ t('aiModels.providers.openai.apiKeyHint') }}</small>
      </div>

      <!-- Model Name -->
      <div class="form-group">
        <label for="openai-model">
          {{ t('aiModels.providers.openai.modelName') }}
        </label>
        <select id="openai-model" v-model="localConfig.modelName">
          <option value="gpt-4">GPT-4</option>
          <option value="gpt-4-turbo">GPT-4 Turbo</option>
          <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
          <option value="gpt-4o">GPT-4o</option>
        </select>
        <small class="hint">{{ t('aiModels.providers.openai.modelHint') }}</small>
      </div>

      <!-- Organization ID (Optional) -->
      <div class="form-group">
        <label for="openai-org">
          {{ t('aiModels.providers.openai.organizationId') }}
          <span class="optional">({{ t('aiModels.optional') }})</span>
        </label>
        <input
          id="openai-org"
          v-model="localConfig.organizationId"
          type="text"
          :placeholder="t('aiModels.providers.openai.organizationPlaceholder')"
        />
        <small class="hint">{{ t('aiModels.providers.openai.organizationHint') }}</small>
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
          :disabled="testing || !localConfig.apiKey"
          class="btn-secondary"
        >
          <span v-if="testing" class="spinner-small"></span>
          {{ testing ? t('aiModels.testing') : t('aiModels.testConnection') }}
        </button>

        <button
          type="submit"
          :disabled="!hasChanges || !localConfig.apiKey"
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

// Local state
const showApiKey = ref(false)
const localConfig = ref<ProviderConfig>({
  apiKey: props.config.apiKey || '',
  modelName: props.config.modelName || 'gpt-4',
  organizationId: props.config.organizationId || ''
})

// Check if config has changes
const hasChanges = computed(() => {
  return (
    localConfig.value.apiKey !== props.config.apiKey ||
    localConfig.value.modelName !== props.config.modelName ||
    localConfig.value.organizationId !== props.config.organizationId
  )
})

// Watch for external config changes
watch(
  () => props.config,
  (newConfig) => {
    if (newConfig.apiKey) {
      localConfig.value.apiKey = newConfig.apiKey
    }
    if (newConfig.modelName) {
      localConfig.value.modelName = newConfig.modelName
    }
    if (newConfig.organizationId !== undefined) {
      localConfig.value.organizationId = newConfig.organizationId
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
.openai-settings {
  max-width: 600px;
}

.openai-settings h3 {
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

.form-group label .optional {
  color: var(--color-text-tertiary);
  font-weight: var(--font-weight-normal);
  font-size: var(--font-size-xs);
}

.input-with-toggle {
  position: relative;
}

.form-group input,
.form-group select {
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-md);
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  transition: border-color 0.2s ease;
  width: 100%;
}

.input-with-toggle input {
  padding-right: calc(var(--space-md) + 40px);
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.toggle-visibility {
  position: absolute;
  right: var(--space-sm);
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: var(--font-size-lg);
  padding: var(--space-xs);
  opacity: 0.6;
  transition: opacity 0.2s ease;
}

.toggle-visibility:hover {
  opacity: 1;
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
