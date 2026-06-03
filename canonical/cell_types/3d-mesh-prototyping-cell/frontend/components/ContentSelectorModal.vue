<script setup lang="ts">
/**
 * ContentSelectorModal.vue
 *
 * Modal for browsing and selecting persisted content (images) from ContentManagerCell.
 * Used by MeshPrototypingCell's View.vue for the "Select Existing" input mode (G5).
 */
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'
import { ContentSelectionCell } from '#canonical/cell_types/content-selection-cell/frontend/ContentSelectionCell'

const logger = createLogger('component:content-selector-modal')

const emit = defineEmits<{
  (e: 'select', content: any): void
  (e: 'close'): void
}>()

const showContentSelector = ref(false)
const availableContents = ref<any[]>([])
const contentsLoading = ref(false)
const contentsError = ref<string | null>(null)

const open = async () => {
  showContentSelector.value = true
  contentsLoading.value = true
  contentsError.value = null

  try {
    const selector = new ContentSelectionCell()
    const result = await selector.execute({
      action: 'list',
      content_type_id: 'image-png',
      limit: 50,
    })
    if (result.success) {
      availableContents.value = (result.output as any).contents || []
    } else {
      contentsError.value = result.error || 'Failed to load contents'
    }
  } catch (err: any) {
    contentsError.value = err.message
  } finally {
    contentsLoading.value = false
  }
}

const handleSelect = (content: any) => {
  emit('select', content)
  showContentSelector.value = false
}

const handleClose = () => {
  showContentSelector.value = false
  emit('close')
}

defineExpose({ open })
</script>

<template>
  <div v-if="showContentSelector"
       class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
       @click.self="handleClose">
    <div class="bg-surface dark:bg-surface-dark rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-auto p-6">
      <h3 class="text-lg font-semibold mb-4">Select Image</h3>

      <!-- Loading -->
      <div v-if="contentsLoading" class="text-center py-8">
        Loading contents...
      </div>

      <!-- Error -->
      <div v-else-if="contentsError" class="text-error mb-4">
        {{ contentsError }}
        <button @click="open" class="ml-2 underline">Retry</button>
      </div>

      <!-- Empty -->
      <div v-else-if="availableContents.length === 0" class="text-center py-8 text-text-secondary">
        No images found. Upload one first.
      </div>

      <!-- Content List -->
      <div v-else class="space-y-2">
        <div v-for="item in availableContents" :key="item.content_id"
             @click="handleSelect(item)"
             class="p-3 rounded border border-border hover:border-primary cursor-pointer transition flex justify-between items-center">
          <div>
            <p class="font-medium">{{ item.filename }}</p>
            <p class="text-xs text-text-secondary">{{ item.size_bytes ? Math.round(item.size_bytes / 1024) + ' KB' : '' }} — {{ item.created_at || '' }}</p>
          </div>
          <span class="text-primary text-sm">Select →</span>
        </div>
      </div>

      <button @click="handleClose"
              class="mt-4 text-text-secondary hover:text-text-primary text-sm">
        Cancel
      </button>
    </div>
  </div>
</template>
