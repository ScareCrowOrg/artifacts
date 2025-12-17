/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-16",
 *   "theme_compliance": 96,
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
      <div class="flex flex-col gap-1">
        <h2 class="m-0 text-2xl text-gray-900 dark:text-gray-100 font-semibold">{{ $t('fileEditor.title') }}</h2>
        <div class="flex items-center gap-1 text-sm">
          <span class="font-semibold text-gray-600 dark:text-gray-400">{{ $t('fileEditor.pathLabel') }}</span>
          <code class="px-1.5 py-0.5 bg-primary/10 border border-primary/20 rounded font-mono text-xs text-primary">
            {{ fullPath }}
          </code>
        </div>
      </div>
      <button
        class="px-3 py-1.5 text-sm text-error font-medium bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-md cursor-pointer transition-all duration-200 hover:bg-error/10 dark:hover:bg-error/20 hover:border-error disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
        :disabled="isSaving"
        :title="$t('fileEditor.closeEditorTooltip')"
        :aria-label="$t('fileEditor.closeEditorAriaLabel', { fileName })"
        @click="handleDeleteEphemeral"
      >
        {{ $t('fileEditor.closeEditorButton') }}
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex-1 flex items-center justify-center text-gray-600 dark:text-gray-400">
      <p>{{ $t('fileEditor.loadingFile') }}</p>
    </div>

    <!-- Editor -->
    <div v-else class="flex-1 min-h-[400px] flex w-full max-w-full">
      <MarkdownEditor
        v-model="fileContent"
        :placeholder="$t('fileEditor.editingPlaceholder', { fileName })"
        :readonly="isSaving"
      />
    </div>

    <!-- Footer Actions -->
    <div class="flex justify-between items-center pt-4 border-t border-gray-200 dark:border-gray-700">
      <div class="flex gap-4 text-xs text-gray-600 dark:text-gray-400">
        <span class="px-2 py-0.5 bg-warning/10 border border-warning/30 rounded text-warning font-semibold whitespace-nowrap">
          {{ $t('fileEditor.ephemeralCellBadge') }}
        </span>
        <span class="whitespace-nowrap">{{ $t('fileEditor.fileLabel') }} {{ fileName }}</span>
      </div>
      
      <!-- Action Buttons -->
      <div class="flex gap-2">
        <!-- Send to Chat Button -->
        <button
          class="px-4 py-2 text-sm font-medium text-primary bg-white dark:bg-gray-900 border border-primary rounded-md cursor-pointer transition-all duration-200 hover:bg-primary/10 dark:hover:bg-primary/20 hover:border-primary-hover disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
          :disabled="isSaving || isLoading || !fileContent"
          :title="$t('fileEditor.sendToChatTooltip')"
          :aria-label="$t('fileEditor.sendToChatAriaLabel', { fileName })"
          @click="handleSendToChat"
        >
          {{ $t('fileEditor.sendToChat') }}
        </button>
        
        <!-- Save Button -->
        <button
          class="px-4 py-2 text-sm font-medium text-white bg-success rounded-md cursor-pointer transition-all duration-200 hover:bg-success/80 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
          :disabled="isSaving || isLoading"
          :title="isSaving ? $t('fileEditor.saving') : $t('fileEditor.saveButton')"
          :aria-label="$t('fileEditor.saveButton') + ' ' + fileName"
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
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, toRef } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import { useFileEditor } from './composables/useFileEditor'
import { useCellsStore } from '@/stores/cells'
import type { FileEditorCell } from '@/types'

const { t: $t } = useI18n()

/**
 * Props interface for File Editor View
 */
interface Props {
  /** The file editor cell instance */
  cell: FileEditorCell
}

const props = defineProps<Props>()

// Stores
const cellsStore = useCellsStore()

// Use file editor composable - pass the cell as a ref using toRef to maintain reactivity
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
} = useFileEditor(toRef(props, 'cell'))

// Sync file content to cell object for CellToolbar access
watch(fileContent, (newContent) => {
  if (props.cell) {
    // Update cell via store instead of mutating props
    cellsStore.updateCellData(props.cell.id, {
      content: newContent,
      filename: fileName.value,
    })
  }
})

/**
 * Handle delete ephemeral button click
 */
function handleDeleteEphemeral(): void {
  deleteEphemeral()
}

/**
 * Handle send to chat (exposed for CellToolbar)
 */
function handleSendToChat(): void {
  console.group('[FILE-EDITOR] 📤 handleSendToChat - DEBUG ITERATION 1')
  console.log('Cell data:', {
    cellId: props.cell?.id,
    fileName: fileName.value,
    contentLength: fileContent.value?.length,
  })
  console.log('[FILE-EDITOR] Calling sendToChat() from composable...')
  sendToChat()
  console.log('[FILE-EDITOR] ✅ sendToChat() completed')
  console.groupEnd()
}

// Load file on mount
onMounted(async () => {
  console.log('[FILE-EDITOR] Component mounted, cell data:', {
    cellId: props.cell?.id,
    cellType: props.cell?.notebook_item_type_id,
    initial_data: props.cell?.initial_data,
    fileName: fileName.value,
    filePath: filePath.value,
    fullPath: fullPath.value
  })
  console.log('[FILE-EDITOR] 📋 Exposing methods via defineExpose:', {
    onSave: 'function',
    onSendToChat: 'function'
  })
  await loadFile()
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
