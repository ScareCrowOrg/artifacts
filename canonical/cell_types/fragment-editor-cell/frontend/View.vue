/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-02-22",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-02-22",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues": 0
 * }
 */
<template>
  <div class="fragment-editor-cell">
    <div class="editor-header">
      <h2 class="editor-title">
        {{ $t('fragmentEditor.title') }}
      </h2>
    </div>

    <div class="editor-body">
      <p class="editor-description">
        {{ $t('fragmentEditor.description') }}
      </p>

      <div class="editor-wrapper">
        <MarkdownEditor
          v-model="fragmentContent"
          :placeholder="$t('fragmentEditor.placeholder')"
          :readonly="isSaving"
        />
      </div>
    </div>

    <div class="editor-footer">
      <button
        class="btn btn-secondary"
        :disabled="isSaving"
        @click="handleCancel"
      >
        {{ $t('fragmentEditor.cancelButton') }}
      </button>
      <button
        class="btn btn-primary"
        :disabled="isSaving || !fragmentContent.trim()"
        @click="handleSave"
      >
        {{ isSaving ? $t('fragmentEditor.savingButton') : $t('fragmentEditor.saveButton') }}
      </button>
    </div>

    <!-- Error Message -->
    <div v-if="errorMessage" class="editor-error">
      {{ errorMessage }}
    </div>

    <!-- Success Message -->
    <div v-if="successMessage" class="editor-success">
      {{ successMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import type { FragmentEditorCell } from './FragmentEditorCell'

const { t } = useI18n()

// Props
interface Props {
  cellInstance: FragmentEditorCell
  initialData?: {
    cellId?: string
    fragmentId?: string
    content?: string
    action?: 'create' | 'edit' | 'load'
  }
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  saved: [data: any]
  cancelled: []
  error: [error: string]
}>()

// State
const fragmentContent = ref(props.initialData?.content || '')
const isSaving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

// Computed
const action = computed(() => {
  if (props.initialData?.action) {
    return props.initialData.action
  }
  return props.initialData?.fragmentId ? 'edit' : 'create'
})

// Watch for initial data changes
watch(
  () => props.initialData?.content,
  (newContent) => {
    if (newContent !== undefined) {
      fragmentContent.value = newContent
    }
  }
)

// Methods
async function handleSave() {
  if (!fragmentContent.value.trim()) {
    errorMessage.value = t('fragmentEditor.errors.emptyContent')
    return
  }

  isSaving.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    const result = await props.cellInstance.execute({
      action: action.value,
      cellId: props.initialData?.cellId,
      fragmentId: props.initialData?.fragmentId,
      content: fragmentContent.value
    })

    if (result.success) {
      successMessage.value = result.output?.message || t('fragmentEditor.success.saved')
      emit('saved', result.output)
      
      // Auto-clear success message after 3 seconds
      setTimeout(() => {
        successMessage.value = ''
      }, 3000)
    } else {
      errorMessage.value = result.error || t('fragmentEditor.errors.saveFailed')
      emit('error', result.error || 'Save failed')
    }
  } catch (err: any) {
    errorMessage.value = err.message || t('fragmentEditor.errors.unknown')
    emit('error', err.message)
  } finally {
    isSaving.value = false
  }
}

function handleCancel() {
  emit('cancelled')
}

// Clear messages when content changes
watch(fragmentContent, () => {
  errorMessage.value = ''
  successMessage.value = ''
})
</script>

<style scoped>
.fragment-editor-cell {
  background: var(--color-surface);
  border-radius: var(--radius-lg, 12px);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  max-width: 700px;
  margin: 0 auto;
}

.editor-header {
  padding: var(--space-md, 1rem) var(--space-lg, 1.5rem);
  border-bottom: 2px solid var(--color-border, #e0e0e0);
}

.editor-title {
  margin: 0;
  font-size: var(--font-size-xl, 1.25rem);
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary, #333);
}

.editor-body {
  padding: var(--space-lg, 1.5rem);
  overflow-y: auto;
  flex: 1;
}

.editor-description {
  margin: 0 0 var(--space-md, 1rem) 0;
  font-size: var(--font-size-sm, 0.875rem);
  color: var(--color-text-secondary, #666);
}

.editor-wrapper {
  min-height: 300px;
  max-height: 400px;
}

.editor-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm, 0.75rem);
  padding: var(--space-md, 1rem) var(--space-lg, 1.5rem);
  border-top: 1px solid var(--color-border, #e0e0e0);
}

.editor-error {
  padding: var(--space-sm, 0.75rem) var(--space-lg, 1.5rem);
  background: var(--color-error-light);
  border-top: 1px solid var(--color-error);
  color: var(--color-error);
  font-size: var(--font-size-sm, 0.875rem);
  animation: slideDown 0.3s ease;
}

.editor-success {
  padding: var(--space-sm, 0.75rem) var(--space-lg, 1.5rem);
  background: var(--color-success-light, #e8f5e9);
  border-top: 1px solid var(--color-success, #4caf50);
  color: var(--color-success, #2e7d32);
  font-size: var(--font-size-sm, 0.875rem);
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.btn {
  padding: var(--space-sm, 0.75rem) var(--space-md, 1rem);
  border: 1px solid var(--color-border, #ddd);
  border-radius: var(--radius-md, 6px);
  font-size: var(--font-size-sm, 0.875rem);
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn:focus {
  outline: 2px solid var(--color-primary, #6200ea);
  outline-offset: 2px;
}

.btn-secondary {
  background: var(--color-surface);
  color: var(--color-text-primary, #333);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-surface-hover, #f5f5f5);
}

.btn-primary {
  background: var(--color-primary, #6200ea);
  color: var(--color-background);
  border-color: var(--color-primary, #6200ea);
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
  box-shadow: var(--shadow-md);
}

/* Responsive */
@media (max-width: 768px) {
  .fragment-editor-cell {
    max-width: 100%;
  }

  .editor-header,
  .editor-body,
  .editor-footer {
    padding: var(--space-sm, 0.75rem) var(--space-md, 1rem);
  }

  .editor-footer {
    flex-direction: column;
  }

  .btn {
    width: 100%;
  }
}
</style>
