/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-11",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="json-editor">
    <div class="editor-header">
      <h3 class="editor-title">{{ $t('admin.jsonEditor.title') }}</h3>
      <div class="editor-actions">
        <button
          class="btn-secondary"
          :disabled="isLoading"
          @click="cancel"
        >
          {{ $t('admin.jsonEditor.cancelButton') }}
        </button>
        <button
          class="btn-primary"
          :disabled="!isValid || isLoading"
          @click="save"
        >
          {{ isLoading ? $t('admin.jsonEditor.savingButton') : $t('admin.jsonEditor.saveButton') }}
        </button>
      </div>
    </div>

    <div class="editor-body">
      <textarea
        v-model="jsonText"
        class="json-textarea"
        :class="{ 'has-error': !isValid }"
        :placeholder="$t('admin.jsonEditor.placeholder')"
        spellcheck="false"
        @input="validateJson"
      ></textarea>

      <div v-if="errorMessage" class="error-message">
        <span class="error-icon">⚠️</span>
        {{ errorMessage }}
      </div>

      <div v-if="isValid && jsonText" class="success-message">
        <span class="success-icon">✓</span>
        {{ $t('admin.jsonEditor.validJson') }}
      </div>
    </div>

    <div class="editor-footer">
      <div class="help-text">
        <span class="help-icon">ℹ️</span>
        {{ $t('admin.jsonEditor.helpText') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, defineProps, defineEmits } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: [Object, Array, String, Number, Boolean, null],
    required: true,
  },
})

const emit = defineEmits(['update:modelValue', 'save', 'cancel'])

// State
const jsonText = ref('')
const isValid = ref(true)
const errorMessage = ref('')
const isLoading = ref(false)

// Initialize with formatted JSON
onMounted(() => {
  try {
    jsonText.value = JSON.stringify(props.modelValue, null, 2)
    isValid.value = true
  } catch {
    jsonText.value = String(props.modelValue)
    errorMessage.value = t('admin.jsonEditor.invalidInitialData')
    isValid.value = false
  }
})

// Watch for external changes
watch(
  () => props.modelValue,
  (newValue) => {
    try {
      jsonText.value = JSON.stringify(newValue, null, 2)
      isValid.value = true
      errorMessage.value = ''
    } catch (err) {
      console.error('[JsonEditor] Error formatting value:', err)
    }
  },
)

// Validate JSON
function validateJson() {
  if (!jsonText.value.trim()) {
    isValid.value = false
    errorMessage.value = t('admin.jsonEditor.jsonCannotBeEmpty')
    return
  }

  try {
    const parsed = JSON.parse(jsonText.value)
    isValid.value = true
    errorMessage.value = ''
    emit('update:modelValue', parsed)
  } catch (err) {
    isValid.value = false
    errorMessage.value = t('admin.jsonEditor.invalidJson', { message: err.message })
  }
}

// Save handler
async function save() {
  if (!isValid.value) {
    return
  }

  isLoading.value = true

  try {
    const parsed = JSON.parse(jsonText.value)
    emit('save', parsed)
  } catch (err) {
    errorMessage.value = t('admin.jsonEditor.failedToSave', { message: err.message })
    isValid.value = false
  } finally {
    isLoading.value = false
  }
}

// Cancel handler
function cancel() {
  emit('cancel')
}

// Auto-format on Ctrl+Alt+F
onMounted(() => {
  const textarea = document.querySelector('.json-textarea')
  if (textarea) {
    textarea.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.altKey && e.key === 'f') {
        e.preventDefault()
        formatJson()
      }
    })
  }
})

// Format JSON
function formatJson() {
  try {
    const parsed = JSON.parse(jsonText.value)
    jsonText.value = JSON.stringify(parsed, null, 2)
    isValid.value = true
    errorMessage.value = ''
  } catch {
    // Keep current text if parsing fails
  }
}
</script>

<style scoped>
.json-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-background);
}

.editor-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.editor-actions {
  display: flex;
  gap: 12px;
}

.btn-primary,
.btn-secondary {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: var(--color-primary);
  color: #ffffff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.btn-primary:disabled {
  background: var(--color-border);
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--color-surface);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-surface-hover);
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.editor-body {
  flex: 1;
  padding: 16px;
  overflow: auto;
  position: relative;
}

.json-textarea {
  width: 100%;
  height: 100%;
  min-height: 400px;
  font-family: var(--font-family-mono);
  font-size: 14px;
  line-height: 1.6;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  resize: vertical;
  background: var(--color-code-bg);
  color: var(--color-code-text);
}

.json-textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary) 10%, transparent);
}

.json-textarea.has-error {
  border-color: var(--color-error);
}

.error-message {
  margin-top: 12px;
  padding: 12px;
  background: color-mix(in srgb, var(--color-error) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-error) 20%, transparent);
  border-radius: 6px;
  color: var(--color-error);
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-icon {
  font-size: 16px;
}

.success-message {
  margin-top: 12px;
  padding: 12px;
  background: color-mix(in srgb, var(--color-success) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-success) 20%, transparent);
  border-radius: 6px;
  color: var(--color-success);
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.success-icon {
  font-size: 16px;
  font-weight: bold;
}

.editor-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  background: var(--color-background);
}

.help-text {
  font-size: 12px;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.help-icon {
  font-size: 14px;
}
</style>
