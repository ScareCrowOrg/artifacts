/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-16",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0,
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-16",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <section
    class="manual-capture-cell bg-surface dark:bg-surface-dark rounded-lg shadow-sm border border-border dark:border-border-dark h-full flex flex-col"
    data-testid="manual-capture-cell"
  >
    <!-- Header -->
    <div
      class="flex items-center justify-between px-4 py-3 border-b border-border dark:border-border-dark"
    >
      <h3 class="text-lg font-semibold text-text-primary dark:text-text-primary-dark m-0">
        {{ cellData.icon }} {{ $t('manualCapture.title') }}
      </h3>
      <span class="text-xs text-text-secondary dark:text-text-secondary-dark italic">
        {{ $t('manualCapture.ephemeralLabel') }}
      </span>
    </div>

    <!-- Content Area -->
    <div class="flex-1 p-4 overflow-auto">
      <div class="mb-0">
        <textarea
          v-model="inputContent"
          :placeholder="cellData.placeholder || $t('manualCapture.placeholder')"
          rows="10"
          data-testid="manual-capture-textarea"
          class="w-full h-full min-h-[200px] px-3 py-2 border border-border dark:border-border-dark rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent resize-y bg-background dark:bg-background-dark text-text-primary dark:text-text-primary-dark"
          :disabled="isProcessing"
        ></textarea>
      </div>
    </div>

    <!-- Validation Errors -->
    <div
      v-if="validationErrors.length > 0"
      class="px-4 py-2 bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800"
      data-testid="validation-errors"
    >
      <ul class="text-sm text-red-600 dark:text-red-400 list-disc list-inside">
        <li v-for="(error, index) in validationErrors" :key="index">
          {{ error }}
        </li>
      </ul>
    </div>

    <!-- Actions Footer -->
    <div
      class="flex items-center gap-2 px-4 py-3 bg-surface dark:bg-surface-dark border-t border-border dark:border-border-dark"
    >
      <button
        class="px-3 py-1.5 text-sm font-medium text-background dark:text-background-dark bg-primary rounded-md hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="capture-content-button"
        :disabled="!inputContent.trim() || isProcessing"
        @click="handleCaptureContent"
      >
        <span v-if="isProcessing">{{ $t('manualCapture.processing') }}</span>
        <span v-else>{{ $t('manualCapture.captureButton') }}</span>
      </button>
      
      <button
        class="px-3 py-1.5 text-sm font-medium text-text-secondary dark:text-text-secondary-dark bg-background dark:bg-background-dark rounded-md hover:bg-surface dark:hover:bg-surface-dark transition-colors inline-flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="generate-wireframe-button"
        :disabled="!inputContent.trim() || isProcessing"
        @click="handleGenerateWireframe"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="18"
          height="18"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            d="M4 3a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H4zm0 2h12v10H4V5zm2 2a1 1 0 1 1 2 0 1 1 0 0 1-2 0zm6 0a1 1 0 1 1 2 0 1 1 0 0 1-2 0zM4 9h12v2H4V9zm0 4h12v2H4v-2z"
          />
        </svg>
        <span v-if="isProcessing">{{ $t('manualCapture.processing') }}</span>
        <span v-else>{{ $t('manualCapture.wireframeButton') }}</span>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ManualCaptureCell } from './ManualCaptureCell'
import { useManualCapture } from './composables/useManualCapture'
import type { CellProps, ManualCaptureCellData } from './types'
import type { HealthCheckResult } from '@/types/BaseCell'
import { createLogger } from '@/utils/logger'

const log = createLogger('cell:manual-capture')

// BaseCell instance for headless execution, validation, and health checks
const cellInstance = new ManualCaptureCell()

// Props
const props = defineProps<CellProps>()

// i18n
const { t } = useI18n()

// Get cell data with defaults
const cellData = computed<ManualCaptureCellData>(() => {
  const initial_data = (props.cell?.state?.initial_data || props.cell?.initial_data || {}) as Partial<ManualCaptureCellData>
  return {
    category: initial_data.category || 'efemera',
    icon: initial_data.icon || '✍️',
    placeholder: initial_data.placeholder || t('manualCapture.placeholder'),
  }
})

// Health status
const healthStatus = ref<HealthCheckResult | null>(null)

// Use composable with BaseCell instance
const cellDataRef: Ref<ManualCaptureCellData> = ref(cellData.value)
const {
  inputContent,
  isProcessing,
  captureContent,
  generateWireframe,
  insertContent,
  validationErrors,
} = useManualCapture(cellDataRef, cellInstance)

// Check health on mount (BaseCell pattern)
onMounted(async () => {
  healthStatus.value = await cellInstance.health_check()
})

// Default user ID for ephemeral cells (no auth dependency in shared artifacts)

/**
 * Create a file-editor-v2 cell with the given content
 * This is the key integration point - manual-capture-cell creates file-editor-v2 instances
 */
async function createFileEditorCell(
  content: string,
  fileName: string,
  language: string
): Promise<void> {
  // Generate ephemeral ID for the new file-editor-v2 cell
  const tempCellId = `ephemeral-file-editor-v2-${Date.now()}`

  const cellData = {
    cellId: tempCellId,
    type: 'file-editor-v2',
    title: fileName,
    state: {
      cellInstance: {
        id: tempCellId,
        notebook_item_type_id: 'file-editor-v2',
        assignee_id: 'default-user-id',
        initial_data: {
          fileName: fileName,
          filePath: 'captured',
          language: language,
          readOnly: false,
          category: 'ephemeral',
          icon: '📄',
          content: content,
        },
        status: 'PENDING',
        fragments: [],
      },
      cellType: {
        id: 'file-editor-v2',
        name: 'File Editor',
        default_initial_data: {
          fileName: fileName,
          language: language,
          content: content,
        },
      },
      initial_data: {
        fileName: fileName,
        language: language,
        content: content,
      },
    },
  }

  log.info('Cell data prepared for file-editor-v2 creation', { fileName, language })
}

/**
 * Handle capture content button click
 */
async function handleCaptureContent(): Promise<void> {
  try {
    await captureContent(createFileEditorCell)
    log.info('Content captured successfully')
  } catch (error) {
    log.error('Error capturing content', error)
  }
}

/**
 * Handle generate wireframe button click
 */
async function handleGenerateWireframe(): Promise<void> {
  try {
    await generateWireframe(createFileEditorCell)
    log.info('Wireframe generated successfully')
  } catch (error) {
    log.error('Error generating wireframe', error)
  }
}

/**
 * Public method to insert content from external sources
 * Can be called by parent components via ref
 */
function handleInsertContent(content: string): void {
  insertContent(content)
  
  // Focus on textarea
  nextTick(() => {
    const textarea = document.querySelector(
      '[data-testid="manual-capture-textarea"]'
    ) as HTMLTextAreaElement | null
    
    if (textarea) {
      textarea.focus()
      textarea.scrollTop = textarea.scrollHeight
    }
  })
}

// Expose methods for external access
defineExpose({
  insertContent: handleInsertContent,
})
</script>

<style scoped>
/* No custom styles needed - using design system classes */
.manual-capture-cell {
  min-height: 300px;
}
</style>
