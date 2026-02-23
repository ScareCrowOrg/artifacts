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
  <div class="cell-list">
    <!-- Loading State -->
    <div v-if="isLoading" class="loading-state">
      <div class="spinner"></div>
      <p>{{ $t('notebookCellList.loadingCells') }}</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="!cells.length" class="empty-state">
      <div class="empty-icon">📭</div>
      <h3>{{ $t('notebookCellList.noCellsTitle') }}</h3>
      <p>{{ $t('notebookCellList.noCellsDescription') }}</p>
    </div>

    <!-- Cell List -->
    <div v-else class="cells-container">
      <div
        v-for="cell in cells"
        :key="cell.id"
        class="cell-card"
        :class="{ 'cell-selected': selectedCellId === cell.id }"
        @click="selectCell(cell)"
      >
        <div class="cell-header">
          <h4 class="cell-title">{{ cell.title || $t('notebookCellList.untitledCell') }}</h4>
          <span class="cell-badge" :class="`badge-${cell.status}`">
            {{ cell.status }}
          </span>
        </div>

        <div class="cell-meta">
          <div class="meta-item">
            <span class="meta-label">{{ $t('notebookCellList.typeLabel') }}</span>
            <span class="meta-value">{{ getTypeName(cell.notebook_item_type_id) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">{{ $t('notebookCellList.idLabel') }}</span>
            <span class="meta-value cell-id">{{ truncateId(cell.id) }}</span>
          </div>
        </div>

        <div v-if="cell.content" class="cell-preview">
          {{ truncateText(cell.content, 150) }}
        </div>

        <div class="cell-footer">
          <span class="footer-date">
            {{ $t('notebookCellList.updatedLabel') }} {{ formatDate(cell.updated_at) }}
          </span>
          <span v-if="cell.fragments?.length" class="footer-badge">
            {{ cell.fragments.length }} {{ cell.fragments.length !== 1 ? $t('notebookCellList.fragmentPlural') : $t('notebookCellList.fragmentSingular') }}
          </span>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="!isLoading && cells.length" class="pagination">
      <button
        class="page-btn"
        :disabled="currentPage === 1"
        @click="$emit('page-change', currentPage - 1)"
      >
        {{ $t('notebookCellList.previousButton') }}
      </button>

      <div class="page-info">
        {{ $t('notebookCellList.pageInfo', { current: currentPage, total: totalPages }) }}
        <span class="total-items">{{ $t('notebookCellList.totalItems', { count: totalItems }) }}</span>
      </div>

      <button
        class="page-btn"
        :disabled="currentPage >= totalPages"
        @click="$emit('page-change', currentPage + 1)"
      >
        {{ $t('notebookCellList.nextButton') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'
import { useI18n } from 'vue-i18n'

const { t: $t } = useI18n()

const props = defineProps({
  cells: {
    type: Array,
    default: () => [],
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
  selectedCellId: {
    type: String,
    default: null,
  },
  currentPage: {
    type: Number,
    default: 1,
  },
  totalPages: {
    type: Number,
    default: 1,
  },
  totalItems: {
    type: Number,
    default: 0,
  },
  notebookItemTypes: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['select-cell', 'page-change'])

// Select cell
function selectCell(cell) {
  emit('select-cell', cell)
}

// Get type name from ID
function getTypeName(typeId) {
  const type = props.notebookItemTypes.find((t) => t.id === typeId)
  return type?.name || typeId?.substring(0, 8) || $t('notebookCellList.unknown')
}

// Truncate ID for display
function truncateId(id) {
  return id?.substring(0, 8) || $t('notebookCellList.notAvailable')
}

// Truncate text
function truncateText(text, maxLength) {
  if (!text) return ''
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text
}

// Format date
function formatDate(dateStr) {
  if (!dateStr) return $t('notebookCellList.notAvailable')
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString()
  } catch {
    return dateStr
  }
}
</script>

<style scoped>
.cell-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-surface);
}

.loading-state,
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-2xl);
  color: var(--color-text-secondary);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--color-border-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.empty-icon {
  font-size: 64px;
  margin-bottom: var(--space-md);
}

.empty-state h3 {
  margin: 0 0 var(--space-sm) 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
}

.empty-state p {
  margin: 0;
  font-size: var(--font-size-sm);
}

.cells-container {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.cell-card {
  padding: var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-base);
  background: var(--color-surface);
}

.cell-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-md);
}

.cell-selected {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}

.cell-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-md);
}

.cell-title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  flex: 1;
}

.cell-badge {
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

.cell-meta {
  display: flex;
  gap: var(--space-md);
  margin-bottom: var(--space-sm);
}

.meta-item {
  display: flex;
  gap: var(--space-xs);
  font-size: var(--font-size-xs);
}

.meta-label {
  color: var(--color-text-secondary);
  font-weight: var(--font-weight-medium);
}

.meta-value {
  color: var(--color-text-primary);
}

.cell-id {
  font-family: var(--font-family-mono);
}

.cell-preview {
  margin: var(--space-md) 0;
  padding: var(--space-md);
  background: var(--color-surface-hover);
  border-left: 3px solid var(--color-primary);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  line-height: var(--line-height-normal);
}

.cell-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  padding-top: var(--space-md);
  border-top: 1px solid var(--color-border-light);
}

.footer-badge {
  background: var(--color-surface-hover);
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-sm);
  font-weight: var(--font-weight-medium);
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface-hover);
}

.page-btn {
  padding: var(--space-sm) var(--space-md);
  background: var(--color-surface);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--transition-base);
}

.page-btn:hover:not(:disabled) {
  background: var(--color-surface-hover);
  border-color: var(--color-text-tertiary);
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  display: flex;
  gap: var(--space-sm);
  align-items: center;
}

.total-items {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}
</style>
