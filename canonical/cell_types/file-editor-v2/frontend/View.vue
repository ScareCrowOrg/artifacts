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
    <!-- Header -->
    <div class="flex justify-between items-start pb-4 border-b-2 border-gray-200 dark:border-gray-700">
      <div class="flex flex-col gap-2 flex-1">
        <h2 class="m-0 text-2xl text-text-primary dark:text-text-primary-dark font-semibold">{{ $t('fileEditor.title') }}</h2>
        
        <!-- File Path Display with Edit and Copy Buttons -->
        <div class="flex flex-col gap-2">
          <div class="flex items-center gap-2">
            <span class="text-sm font-semibold text-text-secondary dark:text-text-secondary-dark">
              {{ $t('fileEditor.pathLabel') }}
            </span>
            <code class="px-2 py-1 bg-primary/10 border border-primary/20 rounded font-mono text-xs text-primary">
              {{ editableFullPath }}
            </code>
            <button
              class="px-3 py-1 text-xs font-medium text-primary bg-surface dark:bg-surface-dark border border-primary rounded-md cursor-pointer transition-all duration-200 hover:bg-primary/10 dark:hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              :title="$t('fileEditor.configurePathTooltip')"
              @click="openConfigDialog"
            >
              ⚙️ {{ $t('fileEditor.configurePathButton') }}
            </button>
            <button
              class="px-3 py-1 text-xs font-medium bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-md cursor-pointer transition-all duration-200 hover:bg-primary/10 dark:hover:bg-primary/20 hover:border-primary disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              :class="pathCopied ? 'text-success border-success' : 'text-text-secondary dark:text-text-secondary-dark'"
              :title="$t('fileEditor.copyPath')"
              :aria-label="$t('fileEditor.copyPath')"
              @click="handleCopyPath"
            >
              {{ pathCopied ? '✓' : '📋' }}
              {{ pathCopied ? $t('fileEditor.pathCopied') : $t('fileEditor.copyPath') }}
            </button>
            <span 
              v-if="isNewFile"
              class="ml-2 px-2 py-0.5 bg-warning/10 border border-warning/30 rounded text-warning font-semibold text-xs"
            >
              {{ $t('fileEditor.newFileBadge') }}
            </span>
          </div>
        </div>
      </div>
      <button
        class="px-3 py-1.5 text-sm text-error font-medium bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-md cursor-pointer transition-all duration-200 hover:bg-error/10 dark:hover:bg-error/20 hover:border-error disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
        :disabled="isSaving"
        :title="$t('fileEditor.closeEditorTooltip')"
        :aria-label="$t('fileEditor.closeEditorAriaLabel', { fileName: editableFileName })"
        @click="handleDeleteEphemeral"
      >
        {{ $t('fileEditor.closeEditorButton') }}
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex-1 flex items-center justify-center text-text-secondary dark:text-text-secondary-dark">
      <p>{{ $t('fileEditor.loadingFile') }}</p>
    </div>

    <!-- Editor -->
    <div v-else class="flex-1 min-h-[400px] flex w-full max-w-full">
      <MarkdownEditor
        v-model="fileContent"
        :placeholder="$t('fileEditor.editingPlaceholder', { fileName: editableFileName })"
        :readonly="isSaving"
      />
    </div>

    <!-- Footer Actions -->
    <div class="flex justify-between items-center pt-4 border-t border-gray-200 dark:border-gray-700">
      <div class="flex gap-4 text-xs text-text-secondary dark:text-text-secondary-dark">
        <span class="px-2 py-0.5 bg-warning/10 border border-warning/30 rounded text-warning font-semibold whitespace-nowrap">
          {{ $t('fileEditor.ephemeralCellBadge') }}
        </span>
        <span class="whitespace-nowrap">{{ $t('fileEditor.fileLabel') }} {{ editableFileName }}</span>
      </div>
      
      <!-- Action Buttons -->
      <div class="flex gap-2">
        <!-- Send to Chat Button -->
        <button
          class="px-4 py-2 text-sm font-medium text-primary bg-surface dark:bg-surface-dark border border-primary rounded-md cursor-pointer transition-all duration-200 hover:bg-primary/10 dark:hover:bg-primary/20 hover:border-primary-hover disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
          :disabled="isSaving || isLoading || !fileContent"
          :title="$t('fileEditor.sendToChatTooltip')"
          :aria-label="$t('fileEditor.sendToChatAriaLabel', { fileName: editableFileName })"
          @click="handleSendToChat"
        >
          {{ $t('fileEditor.sendToChat') }}
        </button>
        
        <!-- Save Button -->
        <button
          class="px-4 py-2 text-sm font-medium text-white bg-success rounded-md cursor-pointer transition-all duration-200 hover:bg-success/80 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
          :disabled="isSaving || isLoading"
          :title="isSaving ? $t('fileEditor.saving') : $t('fileEditor.saveButton')"
          :aria-label="$t('fileEditor.saveButton') + ' ' + editableFileName"
          @click="saveFile"
        >
          {{ isSaving ? $t('fileEditor.saving') : $t('fileEditor.saveButton') }}
        </button>
      </div>
    </div>

    <!-- Error/Success Messages -->
    <div v-if="errorMessage" class="p-3 rounded-md text-sm bg-error/10 border border-error/20 text-error">
      {{ errorMessage }}
    </div>
    <div v-if="successMessage" class="p-3 rounded-md text-sm bg-success/10 border border-success/20 text-success">
      {{ successMessage }}
    </div>

    <!-- File Configuration Dialog -->
    <FileConfigDialog
      v-model:is-open="isConfigDialogOpen"
      :initial-filename="editableFileName"
      :initial-directory="editableFilePath"
      @confirm="handleConfigConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, computed, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownEditor from './components/MarkdownEditor.vue'
import FileConfigDialog from './components/FileConfigDialog.vue'
import { useFileEditor } from './composables/useFileEditor'
import { CELL_FACTORY_KEY, type CellFactory } from '#canonical/shared/cellFactory'

const { t: $t } = useI18n()

/**
 * Props interface for File Editor View
 * DynamicWorkspace passes { cellInstance, cell: { cellTypeName, cellType } }.
 * cellInstance.__initialData contains the data set by cellFactory.addChildCell().
 */
interface Props {
  cell?: Record<string, any>
  cellInstance?: Record<string, any>
}

const props = defineProps<Props>()

// Inject cellFactory for closeCell functionality
const cellFactory = inject<CellFactory>(CELL_FACTORY_KEY)

// Create a local cell ref with initial_data sourced from cellInstance.__initialData
// (set by BaseCell.show() when cellFactory.addChildCell() passes initial data)
const cellRef = ref<{ id?: string; initial_data?: Record<string, any> }>({
  initial_data: {},
})

// Use file editor composable with the local cell ref
const {
  fileContent,
  isLoading,
  isSaving,
  errorMessage,
  successMessage,
  fileName,
  filePath,
  fullPath,
  loadFile,
  saveFile,
  deleteEphemeral,
  sendToChat,
} = useFileEditor(cellRef)

// Editable filename and path (separate from readonly computed values)
const editableFileName = ref<string>(fileName.value)
const editableFilePath = ref<string>(filePath.value)

// File configuration dialog state
const isConfigDialogOpen = ref<boolean>(false)

// Copy path state
const pathCopied = ref<boolean>(false)
let copyTimeoutId: ReturnType<typeof setTimeout> | null = null

// Check if this is a new file creation
const isNewFile = computed<boolean>(() => {
  const data = cellRef.value?.initial_data as any
  return data?.isNewFile === true
})

// Computed full path from editable values
const editableFullPath = computed<string>(() => {
  if (editableFilePath.value && editableFilePath.value.trim()) {
    return `${editableFilePath.value.trim()}/${editableFileName.value.trim()}`
  }
  return editableFileName.value.trim()
})

// Watch for changes in the original values (e.g., when cell is updated externally)
watch(fileName, (newValue) => {
  if (newValue !== editableFileName.value) {
    editableFileName.value = newValue
  }
})

watch(filePath, (newValue) => {
  if (newValue !== editableFilePath.value) {
    editableFilePath.value = newValue
  }
})

// Watch editable fields and update cellRef so saveFile() reads current values
watch([editableFileName, editableFilePath], ([newFileName, newFilePath]) => {
  if (cellRef.value) {
    if (!cellRef.value.initial_data) {
      cellRef.value.initial_data = {}
    }
    cellRef.value.initial_data.fileName = newFileName
    cellRef.value.initial_data.filePath = newFilePath
  }
})

/**
 * Handle delete ephemeral button click
 */
function handleDeleteEphemeral(): void {
  const cellId = props.cell?.cellId
  if (cellId && cellFactory) {
    cellFactory.closeCell(cellId)
  }
}

/**
 * Handle send to chat (exposed for CellToolbar)
 */
function handleSendToChat(): void {
  console.log('[FILE-EDITOR] Calling sendToChat() from composable...')
  sendToChat()
}

/**
 * Open the file configuration dialog
 */
function openConfigDialog(): void {
  isConfigDialogOpen.value = true
}

/**
 * Handle file configuration confirmation from dialog
 */
function handleConfigConfirm(data: { filename: string; directory: string }): void {
  console.log('[FILE-EDITOR] Config confirmed:', data)
  console.log('[FILE-EDITOR] Current values before update:', {
    fileName: editableFileName.value,
    filePath: editableFilePath.value
  })
  
  // Update editable fields with values from dialog
  editableFileName.value = data.filename
  editableFilePath.value = data.directory
  
  console.log('[FILE-EDITOR] Updated values:', {
    fileName: editableFileName.value,
    filePath: editableFilePath.value,
    fullPath: editableFullPath.value
  })
  
  // The watchers will automatically update the cell data
}

/**
 * Copy file path to clipboard
 */
async function handleCopyPath(): Promise<void> {
  try {
    await navigator.clipboard.writeText(editableFullPath.value)
    pathCopied.value = true
    
    // Clear any existing timeout
    if (copyTimeoutId) {
      clearTimeout(copyTimeoutId)
    }
    
    // Reset the copied state after 2 seconds
    copyTimeoutId = setTimeout(() => {
      pathCopied.value = false
      copyTimeoutId = null
    }, 2000)
  } catch (error) {
    console.error('[FILE-EDITOR] Failed to copy path to clipboard:', error)
    // Use i18n for error message
    errorMessage.value = $t('fileEditor.loadFileFailed')  // Reuse existing error key
    setTimeout(() => {
      errorMessage.value = ''
    }, 3000)
  }
}

// Load file on mount
onMounted(async () => {
  // Read initialData from cellInstance.__initialData (set by BaseCell.show()
  // when cellFactory.addChildCell() passes initial data from file-manager)
  const initialData = ((props.cellInstance as any)?.__initialData || {}) as Record<string, any>

  // Populate cellRef with data from cellInstance (file-manager → addChildCell flow)
  cellRef.value = {
    initial_data: {
      fileName: initialData.fileName || 'untitled.md',
      filePath: initialData.filePath || 'docs',
      content: initialData.content,
      language: initialData.language,
      readOnly: initialData.readOnly,
      isNewFile: initialData.isNewFile,
      icon: initialData.icon,
    },
  }

  // Initialize editable fields from the hydrated cell data
  editableFileName.value = fileName.value
  editableFilePath.value = filePath.value

  console.log('[FILE-EDITOR] Component mounted, hydrated from cellInstance.__initialData:', {
    initialData,
    fileName: fileName.value,
    filePath: filePath.value,
    fullPath: fullPath.value,
    hasPreProvidedContent: !!initialData.content,
  })

  await loadFile()
})

// Cleanup on unmount
onBeforeUnmount(() => {
  // Clear any pending timeout to prevent memory leaks
  if (copyTimeoutId) {
    clearTimeout(copyTimeoutId)
    copyTimeoutId = null
  }
})

// Expose methods for parent component (CellToolbar) to call
defineExpose({
  onSave: saveFile,
  onSendToChat: handleSendToChat,
})
</script>

<style scoped>
/* No custom styles needed - using Tailwind utilities */
</style>
