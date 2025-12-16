/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-16",
 *   "theme_compliance": 98,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <div class="flex flex-col h-full bg-surface dark:bg-surface-dark p-6 gap-4 overflow-y-auto">
    <!-- Header -->
    <div class="flex justify-between items-start pb-4 border-b-2 border-gray-200 dark:border-gray-700">
      <div class="flex flex-col gap-1">
        <h2 class="m-0 text-2xl text-text-primary dark:text-text-primary-dark font-semibold">
          📁 Gerenciador de Arquivos
        </h2>
        <div class="flex items-center gap-1 text-sm text-text-secondary dark:text-text-secondary-dark">
          <span class="font-semibold">Célula Efêmera</span>
          <span class="px-2 py-0.5 bg-warning/10 border border-warning/30 rounded text-warning font-semibold">
            ⚡ Não Persistida
          </span>
        </div>
      </div>
    </div>

    <!-- Search Bar -->
    <div class="flex gap-2">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="🔍 Buscar arquivos por nome..."
        class="flex-1 px-3 py-2 border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark placeholder:text-text-secondary dark:placeholder:text-text-secondary-dark focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
        aria-label="Buscar arquivos por nome"
        @input="updateSearchQuery(($event.target as HTMLInputElement).value)"
      />
    </div>

    <!-- Action Buttons -->
    <div class="flex gap-2 flex-wrap">
      <button
        class="px-3 py-2 text-sm font-medium text-white dark:text-text-primary-dark bg-primary dark:bg-primary-dark rounded-md hover:bg-primary-hover dark:hover:bg-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-colors"
        title="Atualizar árvore de arquivos e invalidar cache"
        :disabled="isLoading"
        @click="handleRefresh"
      >
        🔄 {{ isLoading ? 'Atualizando...' : 'Atualizar' }}
      </button>
      
      <button
        class="px-3 py-2 text-sm font-medium text-text-secondary dark:text-text-secondary-dark bg-surface dark:bg-surface-dark rounded-md hover:bg-surface-hover dark:hover:bg-surface-dark border border-border dark:border-border-dark focus:outline-none focus:ring-2 focus:ring-border focus:ring-offset-2 transition-colors"
        title="Recolher todos os diretórios"
        @click="collapseAll"
      >
        📁 Recolher Tudo
      </button>
      
      <button
        class="px-3 py-2 text-sm font-medium text-white dark:text-text-primary-dark bg-success dark:bg-green-700 rounded-md hover:bg-green-600 dark:hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-success focus:ring-offset-2 transition-colors"
        @click="handleCreateNew"
      >
        + Novo
      </button>
      
      <button
        class="px-3 py-2 text-sm font-medium text-white dark:text-text-primary-dark bg-primary dark:bg-primary-dark rounded-md hover:bg-primary-hover dark:hover:bg-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="selectedCount === 0"
        title="Abrir arquivo(s) como célula(s) de edição"
        @click="handleOpenSelected"
      >
        📄 Abrir
        <span
          v-if="selectedCount > 0"
          class="ml-1 px-2 py-0.5 text-xs bg-white dark:bg-gray-800 text-primary dark:text-primary-light rounded-full"
        >
          {{ selectedCount }}
        </span>
      </button>
      
      <!-- ITERATION 2: Send to Chat button -->
      <button
        class="px-3 py-2 text-sm font-medium text-white dark:text-text-primary-dark bg-primary dark:bg-primary-dark rounded-md hover:bg-primary-hover dark:hover:bg-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="selectedCount === 0"
        title="Enviar arquivo(s) selecionado(s) para o chat"
        @click="handleSendToChat"
      >
        💬 Enviar para Chat
        <span
          v-if="selectedCount > 0"
          class="ml-1 px-2 py-0.5 text-xs bg-white dark:bg-gray-800 text-primary dark:text-primary-light rounded-full"
        >
          {{ selectedCount }}
        </span>
      </button>
      
      <button
        class="px-3 py-2 text-sm font-medium text-text-secondary dark:text-text-secondary-dark bg-surface dark:bg-surface-dark rounded-md hover:bg-surface-hover dark:hover:bg-surface-dark border border-border dark:border-border-dark focus:outline-none focus:ring-2 focus:ring-border focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="selectedCount === 0"
        title="Limpar seleção de arquivos"
        @click="clearSelection"
      >
        🗑️ Limpar
      </button>
    </div>

    <!-- File Tree -->
    <div v-if="isLoading" class="flex-1 flex items-center justify-center text-text-secondary dark:text-text-secondary-dark">
      <p>⏳ Carregando árvore de arquivos...</p>
    </div>
    
    <div v-else-if="hasNoMatches" class="flex-1 flex items-center justify-center text-text-secondary dark:text-text-secondary-dark">
      <p>🔍 Nenhum arquivo encontrado para "{{ searchQuery }}"</p>
    </div>
    
    <div v-else class="flex-1 overflow-y-auto border border-border dark:border-border-dark rounded-md p-4 bg-white dark:bg-gray-900">
      <FileTreeNode
        v-for="node in displayTree"
        :key="node.path"
        :node="node"
        :selected-files="selectedFiles"
        :expanded-paths="expandedPaths"
        @toggle-selection="toggleSelection"
        @toggle-expanded="toggleExpanded"
      />
    </div>

    <!-- Status Messages -->
    <div v-if="errorMessage" class="p-3 rounded-md text-sm bg-error/10 border border-error/20 text-error">
      {{ errorMessage }}
    </div>
    <div v-if="successMessage" class="p-3 rounded-md text-sm bg-success/10 border border-success/20 text-success">
      {{ successMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeMount, onBeforeUnmount, onUnmounted, onUpdated } from 'vue'
import { useFileManager } from './composables/useFileManager'
import type { FileManagerCell } from './types'
import FileTreeNode from './components/FileTreeNode.vue'

// Generate unique instance ID for this component instance to track re-mounts
// Using timestamp with random suffix for reliable uniqueness
const instanceId = `FileManagerCell-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
console.log(`[${instanceId}] 🏗️ Component script setup executing`)

/**
 * Props interface for File Manager View
 */
interface Props {
  /** The file manager cell instance */
  cell: FileManagerCell
}

const props = defineProps<Props>()

console.log(`[${instanceId}] 📦 Props received:`, {
  cellId: props.cell?.id,
  cellType: props.cell?.type,
  hasInitialData: !!props.cell?.initial_data
})

// Use file manager composable
const {
  displayTree,
  selectedFiles,
  expandedPaths,
  searchQuery,
  isLoading,
  errorMessage,
  successMessage,
  selectedCount,
  hasNoMatches,
  refreshTree,
  toggleSelection,
  clearSelection,
  toggleExpanded,
  collapseAll,
  updateSearchQuery,
  openSelectedFiles,
  createNewFile,
  sendSelectedToChat  // ITERATION 2: Added send to chat function
} = useFileManager(ref(props.cell))

/**
 * Handle refresh button click
 */
async function handleRefresh(): Promise<void> {
  await refreshTree()
}

/**
 * Handle open selected files
 */
async function handleOpenSelected(): Promise<void> {
  await openSelectedFiles()
}

/**
 * Handle send to chat
 * ITERATION 2: Added for file-manager-cell Send to Chat functionality
 */
async function handleSendToChat(): Promise<void> {
  await sendSelectedToChat()
}

/**
 * Handle create new file
 */
function handleCreateNew(): void {
  const fileName = prompt('Nome do arquivo (com extensão):')
  if (fileName && fileName.trim()) {
    const folder = prompt('Pasta (deixe vazio para "docs"):', 'docs')
    createNewFile(fileName.trim(), folder || 'docs')
  }
}

// Lifecycle hooks for debugging
onBeforeMount(() => {
  console.log(`[${instanceId}] 🔵 onBeforeMount - component about to mount`)
})

onMounted(() => {
  console.log(`[${instanceId}] 🟢 onMounted - component mounted to DOM`)
})

onUpdated(() => {
  console.log(`[${instanceId}] 🔄 onUpdated - component re-rendered`, {
    cellId: props.cell?.id,
    timestamp: new Date().toISOString()
  })
})

onBeforeUnmount(() => {
  console.log(`[${instanceId}] 🟠 onBeforeUnmount - component about to unmount`)
})

onUnmounted(() => {
  console.log(`[${instanceId}] 🔴 onUnmounted - component unmounted`)
})

// Load tree once on initial mount
// Using a flag to ensure it only runs once even if component re-renders
let treeInitialized = false
let watchCallCount = 0
watch(
  () => props.cell,
  (newCell, oldCell) => {
    watchCallCount++
    console.log(`[${instanceId}] 👁️ Watcher triggered (call #${watchCallCount})`, {
      treeInitialized,
      newCellId: newCell?.id,
      oldCellId: oldCell?.id,
      cellChanged: newCell !== oldCell,
      willCallRefresh: !treeInitialized
    })
    
    if (!treeInitialized) {
      treeInitialized = true
      console.log(`[${instanceId}] 🚀 Calling refreshTree() for the first time`)
      refreshTree()
    } else {
      console.log(`[${instanceId}] ⏭️ Skipping refreshTree() - already initialized`)
    }
  },
  { immediate: true }
)
</script>

<style scoped>
/* Custom scrollbar for tree view */
.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: transparent;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.dark .overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}

.dark .overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>
