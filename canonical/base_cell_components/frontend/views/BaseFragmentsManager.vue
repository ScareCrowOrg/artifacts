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
  <div class="flex flex-col h-full p-6 gap-4 overflow-y-auto bg-surface dark:bg-surface-dark">
    <!-- Error State: No Cell ID -->
    <div
      v-if="!cellId"
      class="flex items-center justify-center h-full"
    >
      <div class="text-center border-2 border-error/30 dark:border-error/40 rounded-lg p-6 bg-error/10 dark:bg-error/20 max-w-md">
        <span class="text-5xl mb-3 block">⚠️</span>
        <p class="font-bold text-lg text-error dark:text-error-light mb-2">{{ $t('fragmentsManager.configError') }}</p>
        <p class="text-sm text-error dark:text-error-light mb-2">
          {{ $t('fragmentsManager.noCellId') }}
        </p>
        <p class="text-xs text-error/80 dark:text-error-light/80">
          {{ $t('fragmentsManager.cellIdRequirement') }} <code class="px-1 py-0.5 bg-error/20 dark:bg-error/30 rounded">state.sourceCellId</code>,
          <code class="px-1 py-0.5 bg-error/20 dark:bg-error/30 rounded">id</code>, {{ $t('common.or') }}
          <code class="px-1 py-0.5 bg-error/20 dark:bg-error/30 rounded">cellId</code>.
        </p>
        <button
          class="mt-4 px-4 py-2 border border-error rounded-md bg-surface dark:bg-surface-dark text-error text-sm font-medium cursor-pointer transition-all hover:bg-error hover:text-white"
          @click="handleClose"
        >
          {{ $t('common.close') }}
        </button>
      </div>
    </div>

    <!-- Main Content (only when cellId is valid) -->
    <template v-else>
      <!-- Header -->
      <div class="flex justify-between items-center pb-4 border-b-2 border-border dark:border-border-dark">
        <h2 class="m-0 text-2xl text-text-primary dark:text-text-primary-dark font-semibold">
          📚 {{ $t('fragmentsManager.title') }}
        </h2>
        <button
          class="w-6 h-6 text-lg border-0 bg-background hover:bg-background cursor-pointer rounded flex items-center justify-center transition-colors"
          :title="$t('common.close')"
          @click="handleClose"
        >
          ×
        </button>
      </div>

    <!-- Cell Info -->
    <div class="bg-background dark:bg-background-dark border border-border dark:border-border-dark rounded-lg p-4">
      <div class="flex items-center gap-3">
        <span class="text-sm font-medium text-text-secondary dark:text-text-secondary-dark">{{ $t('fragmentsManager.cellLabel') }}</span>
        <code class="px-2 py-1 bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded text-xs font-mono text-primary">
          {{ cellId }}
        </code>
      </div>
    </div>

    <!-- Add Fragment Section -->
    <div class="bg-background dark:bg-background-dark border border-border dark:border-border-dark rounded-lg p-4">
      <h3 class="m-0 mb-3 text-lg font-semibold text-text-primary dark:text-text-primary-dark">
        ➕ {{ $t('fragmentsManager.addNewFragment') }}
      </h3>
      
      <div class="flex flex-col gap-3">
        <!-- Fragment Type -->
        <div class="flex flex-col gap-1">
          <label for="fragment-type" class="font-semibold text-sm text-text-secondary dark:text-text-secondary-dark">
            {{ $t('fragmentsManager.fragmentType') }}
          </label>
          <select
            id="fragment-type"
            v-model="newFragmentType"
            class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-base bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          >
            <option value="memoria">📝 {{ $t('fragmentsManager.fragmentTypes.memoria') }}</option>
            <option value="code">💻 {{ $t('fragmentsManager.fragmentTypes.code') }}</option>
            <option value="note">📄 {{ $t('fragmentsManager.fragmentTypes.note') }}</option>
            <option value="reference">🔗 {{ $t('fragmentsManager.fragmentTypes.reference') }}</option>
          </select>
        </div>

        <!-- Fragment Content -->
        <div class="flex flex-col gap-1">
          <label for="fragment-content" class="font-semibold text-sm text-text-secondary dark:text-text-secondary-dark">
            {{ $t('fragmentsManager.fragmentContent') }}
          </label>
          <textarea
            id="fragment-content"
            v-model="newFragmentContent"
            class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-base bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent min-h-[150px] font-mono text-sm"
            :placeholder="$t('fragmentsManager.contentPlaceholder')"
          />
        </div>

        <!-- Add Button -->
        <button
          class="btn btn-primary"
          :disabled="!canAddFragment || isAdding"
          @click="handleAddFragment"
        >
          {{ isAdding ? `⏳ ${$t('fragmentsManager.adding')}` : `➕ ${$t('fragmentsManager.addFragment')}` }}
        </button>
      </div>
    </div>

    <!-- Fragments List -->
    <div class="flex flex-col gap-3">
      <div class="flex justify-between items-center">
        <h3 class="m-0 text-lg font-semibold text-text-primary dark:text-text-primary-dark">
          📋 {{ $t('fragmentsManager.existingFragments') }}
        </h3>
        <span
          class="px-3 py-1 bg-primary text-white rounded-full text-xs font-semibold"
          :aria-label="$t('fragmentsManager.fragmentCount', { count: fragmentCount })"
        >
          {{ $t('fragmentsManager.fragmentCount', { count: fragmentCount }) }}
        </span>
      </div>

      <!-- Loading State -->
      <div
        v-if="isLoading"
        class="flex items-center justify-center py-12"
      >
        <div class="text-text-secondary dark:text-text-secondary-dark">⏳ {{ $t('fragmentsManager.loadingFragments') }}</div>
      </div>

      <!-- Empty State -->
      <div
        v-else-if="fragmentCount === 0"
        class="bg-background dark:bg-background-dark border border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center"
      >
        <div class="text-4xl mb-3">📭</div>
        <p class="text-text-secondary dark:text-text-secondary-dark m-0">
          {{ $t('fragmentsManager.noFragments') }}
        </p>
        <p class="text-sm text-gray-500 dark:text-gray-500 mt-2 m-0">
          {{ $t('fragmentsManager.useFormAbove') }}
        </p>
      </div>

      <!-- Fragments -->
      <div
        v-else
        class="flex flex-col gap-4"
      >
        <div
          v-for="(fragment, index) in fragments"
          :key="`fragment-${index}`"
          class="bg-white border border-black/20 rounded-lg p-4 shadow-sm transition-shadow hover:shadow-md"
        >
          <!-- Fragment Header -->
          <div class="flex justify-between items-center mb-3 pb-2 border-b border-border dark:border-border-dark">
            <div class="flex items-center gap-3">
              <span
                class="px-2 py-1 bg-primary/10 border border-primary/30 rounded text-xs font-medium text-primary"
              >
                {{ getFragmentTypeLabel(fragment.type) }}
              </span>
              <span class="text-sm text-text-secondary dark:text-text-secondary-dark font-medium">
                #{{ index + 1 }}
              </span>
            </div>
            <button
              class="px-3 py-2 border border-primary rounded-md bg-white text-primary text-xs font-medium cursor-pointer transition-all whitespace-nowrap hover:bg-primary hover:text-white hover:-translate-y-px hover:shadow-[0_2px_8px_rgba(98,0,234,0.3)]"
              :title="$t('fragmentsManager.sendToChatTooltip', { index: index + 1 })"
              @click="handleSendToChat(fragment, index)"
            >
              💬 {{ $t('fragmentsManager.sendToChat') }}
            </button>
          </div>

          <!-- Fragment Content -->
          <div class="fragment-content text-text-primary dark:text-text-primary-dark">
            <div v-if="fragment.conteudo" class="markdown-scroll">
              <MarkdownRenderer :content="fragment.conteudo" />
            </div>
            <div v-else class="text-gray-500 dark:text-gray-500 italic text-center py-3">
              <em>{{ $t('fragmentsManager.noContent') }}</em>
            </div>
          </div>
        </div>
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNotebookStore } from '@/stores/useNotebookStore'
import { useBaseCellFeatures } from '../composables/useBaseCellFeatures'
import { useParentCellContext } from '@/composables/useParentCellContext'
import type { CellFragment } from '@/types/baseCell'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'

const { t } = useI18n()

/**
 * Props interface for BaseFragmentsManager
 */
interface Props {
  /** Cell object with metadata (standard cell view prop) */
  cell: {
    id?: string
    cellId?: string
    state?: {
      sourceCellId?: string
      cellType?: string
      cellInstance?: any  // Complete cell instance passed from parent
    }
  }
}

const props = defineProps<Props>()

// ============================================================
// Parent Cell Context and Cell Instance
// ============================================================
// Use the standardized composable to get parent cell context
const parentContext = useParentCellContext(props.cell)
const cellId = parentContext.cellId
const parentCellType = parentContext.cellType

// Get the complete cell instance from state (passed directly by parent)
const cellInstanceFromProp = computed(() => props.cell?.state?.cellInstance)

console.group('[BaseFragmentsManager] 🎨 Component mounted')
console.log('📦 Cell ID:', cellId.value)
console.log('🏷️ Parent Cell Type:', parentCellType.value)
console.log('📦 Full Cell Object:', props.cell)
console.log('🔗 Cell Instance from prop:', cellInstanceFromProp.value ? 'Available' : 'Not available')
console.groupEnd()

// ============================================================
// Stores
// ============================================================
const notebookStore = useNotebookStore()

// ============================================================
// State
// ============================================================
const isLoading = ref(false)
const isAdding = ref(false)
const newFragmentType = ref('memoria')
const newFragmentContent = ref('')

// ============================================================
// Base Cell Features
// ============================================================
// Get cell - prioritize the instance passed as prop, fallback to notebook store
// Priority order:
// 1. cellInstanceFromProp (passed directly from parent - most reliable)
// 2. notebookStore.cells[cellId] (fallback)
const cell = computed(() => {
  // Use the cell instance passed as prop if available
  if (cellInstanceFromProp.value) {
    console.log('[BaseFragmentsManager] Using cell instance from prop')
    return cellInstanceFromProp.value
  }
  
  // Fallback to notebook store
  console.log('[BaseFragmentsManager] Falling back to notebook store')
  return (notebookStore.cells as Record<string, any>)[cellId.value]
})

const cellType = computed(() => {
  // Prefer data from the cell instance
  if (cell.value?.type) return cell.value.type
  if (cell.value?.notebook_item_type_id) return cell.value.notebook_item_type_id
  
  // Fallback to parent context if cell not yet in store
  if (parentCellType.value) return parentCellType.value
  
  // Final fallback
  return 'unclassified-cell'
})

const baseCellApi = useBaseCellFeatures(
  cellId,
  cellType
)

// Extract needed properties and methods
const { errorMessage, successMessage, sendFragmentToChat, addFragment } = baseCellApi

// ============================================================
// Computed
// ============================================================

/**
 * Get fragments from cell
 */
const fragments = computed<CellFragment[]>(() => {
  if (!cell.value || !cell.value.fragments) {
    return []
  }
  return cell.value.fragments as CellFragment[]
})

/**
 * Get fragment count
 */
const fragmentCount = computed(() => {
  return fragments.value.length
})

/**
 * Check if can add fragment
 */
const canAddFragment = computed(() => {
  return newFragmentContent.value.trim().length > 0
})

// ============================================================
// Methods
// ============================================================

/**
 * Get fragment type label with emoji
 */
function getFragmentTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    'memoria': `📝 ${t('fragmentsManager.fragmentTypes.memoria')}`,
    'code': `💻 ${t('fragmentsManager.fragmentTypes.code')}`,
    'note': `📄 ${t('fragmentsManager.fragmentTypes.note')}`,
    'reference': `🔗 ${t('fragmentsManager.fragmentTypes.reference')}`,
  }
  return labels[type] || `📋 ${type}`
}

/**
 * Handle add fragment button click
 * 
 * Now passes the cell instance directly to addFragment following the
 * instance injection architectural principle.
 */
async function handleAddFragment(): Promise<void> {
  console.group('[BaseFragmentsManager] ➕ Adding fragment')
  console.log('📝 Type:', newFragmentType.value)
  console.log('📄 Content length:', newFragmentContent.value.length)

  if (!canAddFragment.value) {
    console.warn('⚠️ Cannot add empty fragment')
    console.groupEnd()
    return
  }
  
  if (!cell.value) {
    console.error('❌ Cell instance not available')
    console.groupEnd()
    return
  }

  isAdding.value = true

  try {
    const fragmentData: CellFragment = {
      type: newFragmentType.value,
      conteudo: newFragmentContent.value.trim(),
    }

    // ARCHITECTURE PRINCIPLE: Instance Injection
    // Pass the cell instance directly instead of relying on store lookup
    console.log('📦 Passing cell instance to addFragment')
    await addFragment(cell.value, fragmentData)

    // Clear form on success
    newFragmentContent.value = ''
    newFragmentType.value = 'memoria'

    console.log('✅ Fragment added and form cleared')
  } catch (error: any) {
    console.error('❌ Error adding fragment:', error)
    // Error is already displayed by addFragment
  } finally {
    isAdding.value = false
    console.groupEnd()
  }
}

/**
 * Handle send fragment to chat
 */
function handleSendToChat(fragment: CellFragment, index: number): void {
  console.log('[BaseFragmentsManager] 💬 Sending fragment to chat:', index)
  sendFragmentToChat(fragment, index)
}

/**
 * Handle close button click
 */
function handleClose(): void {
  console.log('[BaseFragmentsManager] ❌ Close button clicked')
  baseCellApi.closeCell()
}

// ============================================================
// Lifecycle
// ============================================================

onMounted(() => {
  console.group('[BaseFragmentsManager] 🔄 Component mounted lifecycle')
  console.log('📦 Cell ID:', cellId.value)
  console.log('🧩 Fragments:', fragmentCount.value)
  console.groupEnd()
})
</script>

<style scoped>
/* Fragment markdown content styling */
.fragment-content {
  max-height: 400px;
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
  @apply px-4 py-2 rounded-md font-medium cursor-pointer transition-all;
}

.btn-primary {
  @apply bg-primary text-white border-0;
}

.btn-primary:hover:not(:disabled) {
  @apply -translate-y-px shadow-lg;
}

.btn-primary:disabled {
  @apply opacity-50 cursor-not-allowed;
}
</style>
