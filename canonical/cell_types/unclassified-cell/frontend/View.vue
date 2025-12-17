/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-17",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-17",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="flex flex-col h-full p-6 gap-4 overflow-y-auto">
    <!-- Header with Toolbar Integration -->
    <div class="flex justify-between items-center pb-4 border-b-2 border-gray-200 dark:border-gray-700">
      <h2 class="m-0 text-2xl text-text-primary dark:text-text-primary-dark font-semibold">
        {{ isNewCell ? $t('unclassifiedCell.newTitle') : $t('unclassifiedCell.editTitle') }}
      </h2>
      <button
        class="w-6 h-6 text-lg border-0 bg-background hover:bg-background cursor-pointer rounded flex items-center justify-center transition-colors"
        :title="$t('unclassifiedCell.closeTooltip')"
        @click="onClose"
      >
        ×
      </button>
    </div>

    <!-- Toolbar Actions -->
    <div class="flex gap-2 mb-2">
      <button
        class="btn btn-primary"
        :disabled="isSaving"
        @click="handleSave"
      >
        {{ isSaving ? $t('unclassifiedCell.saving') : $t('unclassifiedCell.saveButton') }}
      </button>
      <!-- ITERATION 3: Send to Chat button -->
      <button
        class="btn btn-secondary"
        :disabled="isSaving || (!cellData.title && !cellData.content)"
        :title="$t('unclassifiedCell.sendToChatTooltip')"
        @click="handleSendCellToChat"
      >
        {{ $t('unclassifiedCell.sendToChat') }}
      </button>
      <button
        class="btn btn-secondary"
        @click="handleShowFragmentsManager"
      >
        {{ $t('unclassifiedCell.manageFragments') }}
      </button>
      <button
        class="btn btn-secondary"
        @click="handleAddFragment"
      >
        {{ $t('unclassifiedCell.addFragment') }}
      </button>
    </div>

    <!-- Title Input -->
    <div class="flex flex-col gap-1">
      <label for="cell-title" class="font-semibold text-sm text-text-secondary dark:text-text-secondary-dark">
        {{ $t('unclassifiedCell.titleLabel') }}</label
      >
      <input
        id="cell-title"
        v-model="cellData.title"
        type="text"
        class="px-3 py-2 border border-border dark:border-border-dark rounded-md text-base bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed"
        :placeholder="$t('unclassifiedCell.titlePlaceholder')"
        :disabled="isSaving"
      />
    </div>

    <!-- Content Editor -->
    <div class="flex flex-col gap-1 flex-1 min-h-[300px]">
      <label class="font-semibold text-sm text-text-secondary dark:text-text-secondary-dark">{{ $t('unclassifiedCell.contentLabel') }}</label>
      <MarkdownEditor
        v-model="cellData.content"
        :placeholder="$t('unclassifiedCell.contentPlaceholder')"
        :readonly="isSaving"
      />
    </div>

    <!-- Fragment Summary (Compact) -->
    <div
      v-if="fragmentCount > 0"
      class="bg-background border border-border rounded-lg p-3"
    >
      <div class="flex justify-between items-center">
        <span class="text-sm text-text-secondary dark:text-text-secondary-dark" v-html="$t('unclassifiedCell.fragmentSummary', { 
          count: fragmentCount,
          fragmentText: fragmentCount === 1 ? $t('unclassifiedCell.fragmentSingular') : $t('unclassifiedCell.fragmentPlural')
        })"></span>
        <button
          class="px-3 py-1 border border-primary rounded-md bg-surface dark:bg-surface-dark text-primary text-xs font-medium cursor-pointer transition-all hover:bg-primary hover:text-white"
          @click="handleShowFragmentsManager"
        >
          {{ $t('unclassifiedCell.viewFragments') }}
        </button>
      </div>
    </div>

    <!-- Footer Actions -->
    <div class="flex justify-between items-center pt-4 border-t border-gray-200 dark:border-gray-700">
      <div v-if="!isNewCell && cell" class="flex gap-4 text-xs text-text-secondary dark:text-text-secondary-dark">
        <span class="whitespace-nowrap"
          >{{ $t('unclassifiedCell.createdLabel') }} {{ formatDate(cell.created_at) }}</span
        >
        <span class="whitespace-nowrap"
          >{{ $t('unclassifiedCell.updatedLabel') }} {{ formatDate(cell.updated_at) }}</span
        >
      </div>
    </div>

    <!-- Error/Success Messages -->
    <div
      v-if="errorMessage"
      class="p-3 rounded-md text-sm bg-error/10 border border-error/20 text-error"
    >
      {{ errorMessage }}
    </div>
    <div
      v-if="successMessage"
      class="p-3 rounded-md text-sm bg-success/10 border border-success/20 text-success"
    >
      {{ successMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import { useUnclassifiedCell, type UnclassifiedCell } from './composables/useUnclassifiedCell'
import { useBaseCellFeatures } from '#artifacts/canonical/base_cell_components/frontend/composables/useBaseCellFeatures.ts'

const { t: $t } = useI18n()

/**
 * Props interface for Unclassified Cell View
 */
interface Props {
  /** The unclassified cell instance */
  cell: UnclassifiedCell
}

const props = defineProps<Props>()

console.group('[UnclassifiedCellView] 🎨 Component mounted')
console.log('📦 Cell ID:', props.cell?.id || 'NEW')
console.log('📊 Initial data:', props.cell?.initial_data || props.cell?.data)
console.log('🧩 Fragments:', props.cell?.fragments?.length || 0)
console.groupEnd()

// Use unclassified cell composable for cell-specific logic
const {
  cellData,
  isLoading,
  isSaving,
  errorMessage,
  successMessage,
  isNewCell,
  memoryFragments,
  fragmentCount,
  prepareForSave,
  startSaving,
  onSaveComplete,
  onSaveError,
  closeCell,
  sendFragmentToChat,
  sendCellToChat,  // ITERATION 3: Added
  formatDate,
} = useUnclassifiedCell(ref(props.cell))

// Use base cell features for common cell operations
// ARCHITECTURE PRINCIPLE: Pass cell instance to avoid store lookup
const baseCellApi = useBaseCellFeatures(
  computed(() => props.cell?.id || ''),
  computed(() => 'unclassified-cell'),
  {}, // options
  ref(props.cell) // Pass cell instance directly
)

/**
 * Handle close button click
 */
function onClose(): void {
  console.log('[UnclassifiedCellView] ❌ Close button clicked')
  closeCell()
}

/**
 * Handle save button click
 * 
 * FIX for Issue #1206: Now orchestrates save between useUnclassifiedCell
 * and useBaseCellFeatures, passing the cell instance directly to avoid
 * dependency on global "active cell" state.
 */
async function handleSave(): Promise<void> {
  console.group('[UnclassifiedCellView] 💾 Save button clicked')
  
  try {
    // Step 1: Start saving state (show loading indicator)
    startSaving()
    
    // Step 2: Prepare updated cell data from useUnclassifiedCell
    const updatedCell = prepareForSave()
    console.log('📦 Cell data prepared:', {
      id: updatedCell.id,
      hasInitialData: !!updatedCell.initial_data,
      fragmentsCount: updatedCell.fragments?.length || 0,
    })
    
    // Step 3: Save via baseCellApi with the updated cell instance
    // This calls the backend PUT API directly with the cell context
    console.log('📤 Calling baseCellApi.saveCell with cell instance')
    await baseCellApi.saveCell(updatedCell)
    
    // Step 4: Notify success
    console.log('✅ Save completed successfully')
    onSaveComplete()
  } catch (error: any) {
    console.error('❌ Save failed:', error)
    onSaveError(error)
  } finally {
    console.groupEnd()
  }
}

/**
 * Handle save action (exposed for CellToolbar)
 */
async function onSave(): Promise<void> {
  console.log('[UnclassifiedCellView] 💾 Save triggered from toolbar')
  await handleSave()
}

/**
 * Handle show fragments manager button click
 */
function handleShowFragmentsManager(): void {
  console.log('[UnclassifiedCellView] 📚 Show fragments manager clicked')
  baseCellApi.showCellFragmentsManager()
}

/**
 * Handle add fragment button click
 */
function handleAddFragment(): void {
  console.log('[UnclassifiedCellView] ➕ Add fragment clicked')
  // For now, just open the fragments manager
  // In the future, this could open a dedicated "add fragment" modal
  baseCellApi.showCellFragmentsManager()
}

/**
 * Handle send cell to chat button click
 * ITERATION 3: Added for main view Send to Chat functionality
 */
function handleSendCellToChat(): void {
  console.log('[UnclassifiedCellView] 💬 Send cell to chat clicked')
  sendCellToChat()
}

// Expose methods for parent component (CellToolbar) to call
defineExpose({
  onSave,
})
</script>

<style scoped>
/* Fragment markdown content styling */
.fragment-content {
  max-height: 300px;
  overflow-y: auto;
}

.markdown-scroll {
  overflow-y: auto;
}

/* Custom scrollbar for fragments */
.fragment-content::-webkit-scrollbar {
  width: 6px;
}

.fragment-content::-webkit-scrollbar-track {
  background: var(--color-surface-hover);
  border-radius: 3px;
}

.fragment-content::-webkit-scrollbar-thumb {
  background: var(--color-text-secondary);
  border-radius: 3px;
}

.fragment-content::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-primary);
}

/* Button styles */
.btn {
  @apply px-4 py-2 rounded-md font-medium cursor-pointer transition-all border-0;
}

.btn-primary {
  @apply bg-primary text-white dark:bg-primary-hover;
}

.btn-primary:hover:not(:disabled) {
  @apply -translate-y-px shadow-lg dark:bg-primary-light;
}

.btn-primary:disabled {
  @apply opacity-50 cursor-not-allowed;
}

.btn-secondary {
  @apply bg-surface dark:bg-surface-dark text-primary border border-primary;
}

.btn-secondary:hover {
  @apply bg-primary text-white -translate-y-px shadow-md dark:bg-primary-hover;
}
</style>
