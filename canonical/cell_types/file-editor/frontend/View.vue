<template>
  <div class="flex flex-col h-full p-6 gap-4 overflow-y-auto">
    <!-- Header -->
    <div class="flex justify-between items-start pb-4 border-b-2 border-black/20">
      <div class="flex flex-col gap-1">
        <h2 class="m-0 text-2xl text-black font-semibold">📄 Editando Arquivo</h2>
        <div class="flex items-center gap-1 text-sm">
          <span class="font-semibold text-black/60">Caminho:</span>
          <code class="px-1.5 py-0.5 bg-primary/10 border border-primary/20 rounded font-mono text-xs text-primary">
            {{ fullPath }}
          </code>
        </div>
      </div>
      <button
        class="px-3 py-1.5 text-sm text-error font-medium bg-white border border-black/20 rounded-md cursor-pointer transition-all duration-200 hover:bg-error/10 hover:border-error disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
        :disabled="isSaving"
        :title="'Fechar editor (não afeta o arquivo)'"
        :aria-label="'Fechar editor do arquivo ' + fileName"
        @click="handleDeleteEphemeral"
      >
        ❌ Fechar Editor
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex-1 flex items-center justify-center text-black/60">
      <p>⏳ Carregando arquivo...</p>
    </div>

    <!-- Editor -->
    <div v-else class="flex-1 min-h-[400px] flex w-full max-w-full">
      <MarkdownEditor
        v-model="fileContent"
        :placeholder="`Editando ${fileName}...`"
        :readonly="isSaving"
      />
    </div>

    <!-- Footer Actions -->
    <div class="flex justify-between items-center pt-4 border-t border-black/20">
      <div class="flex gap-4 text-xs text-black/60">
        <span class="px-2 py-0.5 bg-warning/10 border border-warning/30 rounded text-warning font-semibold whitespace-nowrap">
          ⚡ Célula Efêmera
        </span>
        <span class="whitespace-nowrap">Arquivo: {{ fileName }}</span>
      </div>
      
      <!-- Save Button -->
      <button
        class="px-4 py-2 text-sm font-medium text-white bg-success rounded-md cursor-pointer transition-all duration-200 hover:bg-success/80 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
        :disabled="isSaving || isLoading"
        :title="isSaving ? 'Salvando...' : 'Salvar alterações no arquivo'"
        :aria-label="'Salvar arquivo ' + fileName"
        @click="saveFile"
      >
        {{ isSaving ? '⏳ Salvando...' : '💾 Salvar' }}
      </button>
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
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import { useFileEditor } from './composables/useFileEditor'
import { useCellsStore } from '@/stores/cells'
import type { FileEditorCell } from '@/types'

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
    cellsStore.updateCell(props.cell.id, {
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
  sendToChat()
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
