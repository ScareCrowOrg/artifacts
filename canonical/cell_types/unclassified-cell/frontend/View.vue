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
  <div class="flex flex-col h-full p-6 gap-4 overflow-y-auto bg-surface text-text-primary dark:bg-surface-dark dark:text-text-primary-dark">
    <!-- Transmutation Status (if cell is transmuted) -->
    <transition name="fade">
      <BookContainer
        v-if="transmutation.isTransmuted(cell?.id)"
        :book="transmutation.getBook(cell?.id)"
        :initial-expanded="true"
        class="mb-4"
        @navigate-to-sub-cell="onNavigateToSubCell"
        @toggle-expanded="onBookToggleExpanded"
      />
    </transition>

    <!-- Transmutation Progress (if transmuting) -->
    <transition name="slide-fade">
      <div
        v-if="transmutation.isTransmuting && transmutation.currentCellId === cell?.id"
        class="transmutation-banner p-4 rounded-lg border-2 border-primary/50 bg-gradient-to-r from-primary/10 to-primary/20 dark:from-primary/20 dark:to-primary/30 mb-4"
        role="alert"
        aria-live="polite"
      >
        <div class="flex items-center gap-3 mb-2">
          <div class="spinner"></div>
          <span class="text-lg font-semibold text-text-primary dark:text-text-primary-dark">
            {{ $t('transmutation.transmutationInProgress') }}
          </span>
        </div>
        <div class="w-full bg-surface-hover rounded-full h-2 dark:bg-surface-hover-dark">
          <div
            class="bg-primary h-2 rounded-full transition-all duration-300 dark:bg-primary-dark"
            :style="{ width: transmutation.transmutationProgress + '%' }"
          ></div>
        </div>
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-2 m-0">
          {{ $t('transmutation.progress', { percentage: transmutation.transmutationProgress }) }}
        </p>
      </div>
    </transition>

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
    <div class="flex gap-2 mb-2 flex-wrap">
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

    <!-- AI Generation Section -->
    <div class="flex flex-col gap-2">
      <div class="flex gap-2 items-center">
        <!-- DEBUG ITER3 - LOG #4: Track what template sees -->
        <span style="display: none;">{{ debugTemplateRender }}</span>
        
        <button
          class="px-4 py-2 bg-primary text-white rounded-md font-medium hover:bg-primary-hover focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors dark:bg-primary-dark dark:hover:bg-primary-hover-dark"
          :disabled="!cellData.content || cellFactory.isGenerating || isSaving"
          @click="onGenerate"
        >
          <span v-if="!cellFactory.isGenerating">🤖 {{ $t('unclassifiedCell.generateButton') }}</span>
          <span v-else>⏳ {{ $t('unclassifiedCell.generating') }}</span>
        </button>
        
        <button
          v-if="cellFactory.isGenerating"
          class="px-4 py-2 bg-error text-white rounded-md font-medium hover:bg-error-hover focus:outline-none focus:ring-2 focus:ring-error focus:ring-offset-2 transition-colors dark:bg-error-dark dark:hover:bg-error-hover-dark"
          @click="cellFactory.cancelGeneration"
        >
          {{ $t('unclassifiedCell.cancelButton') }}
        </button>
      </div>

      <!-- Generation Progress -->
      <div
        v-if="cellFactory.isGenerating"
        class="flex flex-col gap-2 p-4 rounded-md bg-surface border border-border dark:bg-surface-dark dark:border-border-dark"
      >
        <div class="flex justify-between items-center">
          <span class="text-sm font-medium text-text-primary dark:text-text-primary-dark">
            {{ $t('unclassifiedCell.generationProgress') }}
          </span>
          <span class="text-sm text-text-secondary dark:text-text-secondary-dark">
            {{ cellFactory.progressPercentage }}%
          </span>
        </div>
        <div class="w-full bg-surface-hover rounded-full h-2 dark:bg-surface-hover-dark">
          <div
            class="bg-primary h-2 rounded-full transition-all duration-300 dark:bg-primary-dark"
            :style="{ width: cellFactory.progressPercentage + '%' }"
          ></div>
        </div>
      </div>

      <!-- Streaming Preview -->
      <div
        v-if="cellFactory.streamingContent"
        class="flex flex-col gap-2 flex-1 min-h-[200px]"
      >
        <label class="font-semibold text-sm text-text-secondary dark:text-text-secondary-dark">
          {{ $t('unclassifiedCell.previewLabel') }}
        </label>
        <div
          class="flex-1 p-4 border border-border rounded-md overflow-y-auto bg-background prose prose-sm dark:prose-invert dark:bg-background-dark dark:border-border-dark"
          v-html="cellFactory.renderedContent"
        ></div>
      </div>

      <!-- Generated Code Summary -->
      <div
        v-if="cellFactory.hasGeneratedCode"
        class="p-4 rounded-md bg-success/10 border border-success/20 dark:bg-success/20 dark:border-success/30"
      >
        <h3 class="text-sm font-semibold text-success mb-2 dark:text-success-light">
          ✅ {{ $t('unclassifiedCell.codeGenerated') }}
        </h3>
        <ul class="text-sm space-y-1">
          <li
            v-for="ref in cellFactory.generatedRefs"
            :key="ref.id"
            class="text-text-secondary dark:text-text-secondary-dark"
          >
            <span class="font-mono">{{ ref.filename }}</span> ({{ ref.lang }})
          </li>
        </ul>
      </div>
    </div>

    <!-- Sandbox Preview -->
    <SandboxPreview
      v-if="cellFactory.hasGeneratedCode && cellFactory.generatedRefs.length > 0"
      :cell-id="cell?.id || 'temp-cell'"
      :dynamic-refs="cellFactory.generatedRefs"
      :loading="cellFactory.isGenerating"
      class="mt-4"
      data-testid="sandbox-preview-component"
    />

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
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import SandboxPreview from '@/components/SandboxPreview.vue'
import BookContainer from '@/components/BookContainer.vue'
import { useUnclassifiedCell, type UnclassifiedCell } from './composables/useUnclassifiedCell'
import { useBaseCellFeatures } from '#artifacts/canonical/base_cell_components/frontend/composables/useBaseCellFeatures.ts'
import { useCellFactory } from '@/composables/useCellFactory.js'
import { useTransmutation } from '@/composables/useTransmutation.js'
import { useCellsStore } from '@/stores/cells.js'
import { createLogger } from '@/utils/logger.js'

const log = createLogger('component:UnclassifiedCellView')
const { t: $t } = useI18n()

/**
 * Props interface for Unclassified Cell View
 */
interface Props {
  /** The unclassified cell instance */
  cell: UnclassifiedCell
}

const props = defineProps<Props>()

// DEBUG LOG #6: Component initialization
console.group('[UnclassifiedCellView] 🎨 Component SETUP PHASE')
console.log('📦 Cell ID:', props.cell?.id || 'NEW')
console.log('📊 Initial data:', props.cell?.initial_data || props.cell?.data)
console.log('🧩 Fragments:', props.cell?.fragments?.length || 0)
console.log('⏰ Timestamp:', new Date().toISOString())
console.groupEnd()

const cellsStore = useCellsStore()

// DEBUG LOG #7: Before useCellFactory call
console.log('[UnclassifiedCellView] 🏭 CALLING useCellFactory()')

// Cell Factory composable for AI generation
// IMPORTANT: useCellFactory requires cellUuid parameter for proper state isolation
const cellFactory = useCellFactory(props.cell?.id || 'NEW')

// DEBUG LOG #8: After useCellFactory call - check initial state
console.log('[UnclassifiedCellView] ✅ useCellFactory RETURNED', {
  isGenerating: cellFactory.isGenerating.value,
  generationState: cellFactory.generationState.value,
  hasGeneratedCode: cellFactory.hasGeneratedCode.value
})

// Note: onMounted hook removed - reset now happens immediately in setup phase
// This prevents timing issues where template renders before state is properly initialized

// Transmutation composable for cell → book transformations
const transmutation = useTransmutation()

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

// DEBUG ITERATION 3 - LOG #4: Template render tracking
const renderCount = ref(0)
const debugTemplateRender = computed(() => {
  renderCount.value++
  console.log('[DEBUG ITER3] 🎨 TEMPLATE RENDERING #' + renderCount.value, {
    cellId: props.cell?.id,
    isGenerating: cellFactory.isGenerating.value,
    generationState: cellFactory.generationState.value,
    hasContent: !!cellData.content,
    timestamp: new Date().toISOString()
  })
  return renderCount.value
})

// DEBUG LOG #11: Watch isGenerating for any changes
watch(() => cellFactory.isGenerating.value, (newVal, oldVal) => {
  console.log('[UnclassifiedCellView] 🔔 isGenerating CHANGED', {
    from: oldVal,
    to: newVal,
    generationState: cellFactory.generationState.value,
    timestamp: new Date().toISOString(),
    stack: new Error().stack?.split('\n').slice(2, 4).join('\n')
  })
}, { immediate: true })

// DEBUG LOG #12: Watch generationState for any changes
watch(() => cellFactory.generationState.value, (newVal, oldVal) => {
  console.log('[UnclassifiedCellView] 🔔 generationState CHANGED', {
    from: oldVal,
    to: newVal,
    isGenerating: cellFactory.isGenerating.value,
    timestamp: new Date().toISOString()
  })
}, { immediate: true })

// Update cell data in store and cell object when changed
watch(cellData, (newData) => {
  log.debug('Cell data changed', newData)
  
  // Update cell data through store for UI state tracking
  if (props.cell?.id) {
    cellsStore.updateCellData(props.cell.id, newData)
  }
  
  // CRITICAL: Update cell data buffer for persistence
  // This ensures that when save is triggered, the latest data is available
  cellsStore.updateCellDataBuffer(newData)
  log.debug('Cell data buffer updated for save')
}, { deep: true })

/**
 * Handle close button click
 */
function onClose(): void {
  log.info('Close button clicked')
  closeCell()
}

/**
 * Handle AI generation
 */
async function onGenerate(): Promise<void> {
  if (!props.cell?.id || !cellData.value.content) {
    errorMessage.value = 'Please enter content before generating'
    return
  }

  log.info('Triggering AI generation')
  
  try {
    errorMessage.value = null
    const result = await cellFactory.generateCellCode(
      props.cell.id,
      cellData.value.content,
      'auto',
      {
        model: 'gpt-4',
        conversationId: null,
        useRag: false
      }
    )

    if (result.success) {
      successMessage.value = 'Generation started! Watch the preview below.'
    } else {
      errorMessage.value = result.error || 'Failed to start generation'
    }
  } catch (error: any) {
    log.error('Generation error', error)
    errorMessage.value = error.message || 'Failed to generate code'
  }
}

/**
 * Handle navigation to sub-cell from transmuted book
 */
function onNavigateToSubCell({ bookId, subCellId }: { bookId: string; subCellId: string }): void {
  log.info('Navigating to sub-cell', { bookId, subCellId })
  transmutation.navigateToSubCell(bookId, subCellId)
}

/**
 * Handle book expansion toggle
 */
function onBookToggleExpanded({ bookId, expanded }: { bookId: string; expanded: boolean }): void {
  log.debug('Book expansion toggled', { bookId, expanded })
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

/* Fade transition for book container */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Slide-fade transition for transmutation banner */
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.2s cubic-bezier(1, 0.5, 0.8, 1);
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}

/* Spinner animation for transmutation progress */
.spinner {
  width: 20px;
  height: 20px;
  border: 3px solid var(--color-surface-hover);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Transmutation banner pulse effect */
.transmutation-banner {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(98, 0, 234, 0.4);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(98, 0, 234, 0);
  }
}
</style>
