/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-12",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues": 0
 * }
 */
<template>
  <div class="cell-details">
    <div class="details-header">
      <div class="header-title">
        <h2 class="cell-title">{{ cell?.title || $t('notebookCellDetails.title') }}</h2>
        <span class="cell-id">{{ $t('notebookCellDetails.idLabel') }} {{ cell?.id }}</span>
      </div>
      <div class="header-actions">
        <button
          v-if="!isEditMode"
          class="btn-edit"
          :disabled="isLoading"
          @click="enterEditMode"
        >
          {{ $t('notebookCellDetails.editButton') }}
        </button>
        <button
          class="btn-close"
          :aria-label="$t('notebookCellDetails.closeAriaLabel')"
          @click="$emit('close')"
        >
          ✕
        </button>
      </div>
    </div>

    <div class="details-body">
      <!-- Metadata Section -->
      <div class="metadata-section">
        <h3 class="section-title">{{ $t('notebookCellDetails.metadataTitle') }}</h3>
        <div class="metadata-grid">
          <div class="metadata-item">
            <span class="metadata-label">{{ $t('notebookCellDetails.typeIdLabel') }}</span>
            <span class="metadata-value">{{ cell?.notebook_item_type_id }}</span>
          </div>
          <div class="metadata-item">
            <span class="metadata-label">{{ $t('notebookCellDetails.stateLabel') }}</span>
            <span class="metadata-value badge" :class="`badge-${cell?.status}`">
              {{ cell?.status }}
            </span>
          </div>
          <div class="metadata-item">
            <span class="metadata-label">{{ $t('notebookCellDetails.assigneeLabel') }}</span>
            <span class="metadata-value">{{ cell?.assignee_id }}</span>
          </div>
          <div class="metadata-item">
            <span class="metadata-label">{{ $t('notebookCellDetails.createdLabel') }}</span>
            <span class="metadata-value">{{ formatDate(cell?.created_at) }}</span>
          </div>
          <div class="metadata-item">
            <span class="metadata-label">{{ $t('notebookCellDetails.updatedLabel') }}</span>
            <span class="metadata-value">{{ formatDate(cell?.updated_at) }}</span>
          </div>
          <div class="metadata-item">
            <span class="metadata-label">{{ $t('notebookCellDetails.versionLabel') }}</span>
            <span class="metadata-value">{{ cell?.version || $t('notebookCellDetails.notAvailable') }}</span>
          </div>
        </div>
      </div>

      <!-- Content Section -->
      <div v-if="cell?.content" class="content-section">
        <h3 class="section-title">{{ $t('notebookCellDetails.contentTitle') }}</h3>
        <div class="content-box">{{ cell.content }}</div>
      </div>

      <!-- Initial Data Section -->
      <div class="data-section">
        <h3 class="section-title">{{ $t('notebookCellDetails.initialDataTitle') }}</h3>
        <div v-if="!isEditMode" class="data-viewer">
          <JsonViewer :data="cell?.initial_data || {}" />
        </div>
        <div v-else class="data-editor">
          <JsonEditor
            v-model="editedData"
            @save="saveChanges"
            @cancel="cancelEdit"
          />
        </div>
      </div>

      <!-- Fragments Section -->
      <div v-if="cell?.fragments?.length" class="fragments-section">
        <h3 class="section-title">{{ $t('notebookCellDetails.fragmentsTitle') }} ({{ cell.fragments.length }})</h3>
        <div class="fragments-list">
          <div
            v-for="(fragment, index) in cell.fragments"
            :key="index"
            class="fragment-item"
          >
            <div class="fragment-header">
              <span class="fragment-index">#{{ index + 1 }}</span>
              <span class="fragment-type">{{ getFragmentType(fragment) }}</span>
            </div>
            <div class="fragment-content">
              <JsonViewer v-if="isObject(fragment)" :data="fragment" />
              <pre v-else class="fragment-text">{{ fragment }}</pre>
            </div>
          </div>
        </div>
      </div>

      <!-- Refs Section -->
      <div v-if="cell?.refs && Object.keys(cell.refs).length" class="refs-section">
        <h3 class="section-title">{{ $t('notebookCellDetails.referencesTitle') }}</h3>
        <JsonViewer :data="cell.refs" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, defineProps, defineEmits, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import JsonViewer from './JsonViewer.vue'
import JsonEditor from './JsonEditor.vue'

const { t: $t } = useI18n()

const props = defineProps({
  cell: {
    type: Object,
    required: true,
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close', 'update'])

// State
const isEditMode = ref(false)
const editedData = ref(null)

// Watch for cell changes
watch(
  () => props.cell,
  (newCell) => {
    if (newCell && isEditMode.value) {
      editedData.value = JSON.parse(JSON.stringify(newCell.initial_data || {}))
    }
  },
  { immediate: true },
)

// Enter edit mode
function enterEditMode() {
  isEditMode.value = true
  editedData.value = JSON.parse(JSON.stringify(props.cell.initial_data || {}))
}

// Cancel edit mode
function cancelEdit() {
  isEditMode.value = false
  editedData.value = null
}

// Save changes
function saveChanges(newData) {
  emit('update', {
    initial_data: newData,
  })
  isEditMode.value = false
}

// Format date
function formatDate(dateStr) {
  if (!dateStr) return $t('notebookCellDetails.notAvailable')
  try {
    const date = new Date(dateStr)
    return date.toLocaleString()
  } catch {
    return dateStr
  }
}

// Check if value is object
function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

// Get fragment type
function getFragmentType(fragment) {
  if (typeof fragment === 'string') return $t('notebookCellDetails.fragmentTypeString')
  if (Array.isArray(fragment)) return $t('notebookCellDetails.fragmentTypeArray')
  if (isObject(fragment)) return $t('notebookCellDetails.fragmentTypeObject')
  return typeof fragment
}
</script>

<style scoped>
.cell-details {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-surface);
}

.details-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-lg);
  border-bottom: 2px solid var(--color-border);
  background: var(--color-background);
}

.header-title {
  flex: 1;
}

.cell-title {
  margin: 0 0 4px 0;
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.cell-id {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  font-family: var(--font-family-mono);
}

.header-actions {
  display: flex;
  gap: var(--space-md);
}

.btn-edit,
.btn-close {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: none;
}

.btn-edit {
  background: var(--color-primary);
  color: var(--color-text-on-primary);
}

.btn-edit:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.btn-edit:disabled {
  background: var(--color-border);
  cursor: not-allowed;
}

.btn-close {
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xl);
  padding: var(--space-xs) var(--space-sm);
}

.btn-close:hover {
  color: var(--color-text-primary);
  background: var(--color-surface-hover);
}

.details-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-lg);
}

.section-title {
  margin: 0 0 var(--space-md) 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--space-sm);
}

.metadata-section,
.content-section,
.data-section,
.fragments-section,
.refs-section {
  margin-bottom: var(--space-xl);
}

.metadata-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--space-md);
}

.metadata-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.metadata-label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  text-transform: uppercase;
}

.metadata-value {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.badge {
  display: inline-block;
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  text-transform: uppercase;
}

.badge-PENDENTE {
  background: var(--color-warning-light);
  color: var(--color-warning);
}

.badge-EXECUTANDO {
  background: var(--color-info-light);
  color: var(--color-info);
}

.badge-FINALIZADO {
  background: var(--color-success-light);
  color: var(--color-success-dark);
}

.badge-ERRO {
  background: var(--color-error-light);
  color: var(--color-error-dark);
}

.content-box {
  padding: var(--space-md);
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  white-space: pre-wrap;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.data-viewer,
.data-editor {
  padding: var(--space-md);
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.fragments-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.fragment-item {
  padding: var(--space-md);
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.fragment-header {
  display: flex;
  gap: var(--space-md);
  margin-bottom: var(--space-sm);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--color-border);
}

.fragment-index {
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}

.fragment-type {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  text-transform: uppercase;
}

.fragment-content {
  font-size: var(--font-size-sm);
}

.fragment-text {
  margin: 0;
  white-space: pre-wrap;
  font-family: var(--font-family-mono);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}
</style>
