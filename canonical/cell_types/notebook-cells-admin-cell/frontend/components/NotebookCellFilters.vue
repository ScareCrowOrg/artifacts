/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-12",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="cell-filters">
    <div class="filters-row">
      <!-- Status Filter -->
      <div class="filter-group">
        <label for="status-filter" class="filter-label">{{ $t('admin.notebookCellFilters.statusLabel') }}</label>
        <select
          id="status-filter"
          v-model="localFilters.status"
          class="filter-select"
          @change="emitFilters"
        >
          <option value="all">{{ $t('admin.notebookCellFilters.statusAll') }}</option>
          <option value="pendente">{{ $t('admin.notebookCellFilters.statusPending') }}</option>
          <option value="executando">{{ $t('admin.notebookCellFilters.statusExecuting') }}</option>
          <option value="finalizado">{{ $t('admin.notebookCellFilters.statusFinished') }}</option>
          <option value="erro">{{ $t('admin.notebookCellFilters.statusError') }}</option>
        </select>
      </div>

      <!-- Notebook Item Type Filter -->
      <div class="filter-group">
        <label for="type-filter" class="filter-label">{{ $t('admin.notebookCellFilters.itemTypeLabel') }}</label>
        <select
          id="type-filter"
          v-model="localFilters.notebookItemTypeId"
          class="filter-select"
          :disabled="isLoadingTypes"
          @change="emitFilters"
        >
          <option value="all">{{ $t('admin.notebookCellFilters.allTypes') }}</option>
          <option
            v-for="type in notebookItemTypes"
            :key="type.id"
            :value="type.id"
          >
            {{ type.name }}
          </option>
        </select>
      </div>

      <!-- Search Filter -->
      <div class="filter-group filter-search">
        <label for="search-filter" class="filter-label">{{ $t('admin.notebookCellFilters.searchLabel') }}</label>
        <input
          id="search-filter"
          v-model="localFilters.searchText"
          type="text"
          class="filter-input"
          :placeholder="$t('admin.notebookCellFilters.searchPlaceholder')"
          @input="debounceSearch"
        />
      </div>

      <!-- Reset Button -->
      <button
        class="btn-reset"
        :title="$t('admin.notebookCellFilters.resetTitle')"
        @click="resetFilters"
      >
        {{ $t('admin.notebookCellFilters.resetButton') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, defineProps, defineEmits, watch } from 'vue'

const props = defineProps({
  filters: {
    type: Object,
    required: true,
  },
  notebookItemTypes: {
    type: Array,
    default: () => [],
  },
  isLoadingTypes: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:filters', 'reset'])

// Local filters state
const localFilters = ref({ ...props.filters })

// Debounce timer for search
let searchTimeout = null

// Watch for external filter changes
watch(
  () => props.filters,
  (newFilters) => {
    localFilters.value = { ...newFilters }
  },
  { deep: true },
)

// Emit filter changes
function emitFilters() {
  emit('update:filters', { ...localFilters.value })
}

// Debounce search input
function debounceSearch() {
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }

  searchTimeout = setTimeout(() => {
    emitFilters()
  }, 500) // 500ms debounce
}

// Reset all filters
function resetFilters() {
  localFilters.value = {
    status: 'all',
    notebookItemTypeId: 'all',
    searchText: '',
  }
  emit('reset')
}
</script>

<style scoped>
.cell-filters {
  padding: var(--space-md);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.filters-row {
  display: flex;
  align-items: flex-end;
  gap: var(--space-md);
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  min-width: 150px;
}

.filter-search {
  flex: 1;
  min-width: 250px;
}

.filter-label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  text-transform: uppercase;
}

.filter-select,
.filter-input {
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  background: var(--color-surface);
  color: var(--color-text-primary);
  transition: border-color var(--transition-base);
}

.filter-select:focus,
.filter-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}

.filter-select:disabled {
  background: var(--color-surface-hover);
  cursor: not-allowed;
  opacity: 0.6;
}

.filter-input::placeholder {
  color: var(--color-text-tertiary);
}

.btn-reset {
  padding: var(--space-sm) var(--space-md);
  background: var(--color-surface);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--transition-base);
  height: 38px;
}

.btn-reset:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-text-tertiary);
}

@media (max-width: 768px) {
  .filters-row {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-group,
  .filter-search {
    width: 100%;
    min-width: auto;
  }

  .btn-reset {
    width: 100%;
  }
}
</style>
