<template>
  <div class="flex flex-col gap-2 h-full overflow-y-auto">
    <!-- Search -->
    <div class="sticky top-0 bg-surface dark:bg-surface-dark p-2 border-b border-border dark:border-border-dark">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search types..."
        class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary"
      />
    </div>
    
    <!-- Type list -->
    <div class="flex flex-col gap-1 px-2">
      <button
        v-for="type in filteredTypes"
        :key="type.id"
        class="flex flex-col gap-1 p-3 text-left rounded-md transition-colors"
        :class="[
          selectedTypeId === type.id
            ? 'bg-primary/20 border-2 border-primary dark:border-primary-dark'
            : 'bg-surface-hover dark:bg-surface border border-border dark:border-border-dark hover:border-primary dark:hover:border-primary-dark'
        ]"
        :disabled="disabled"
        @click="$emit('select-type', type.id)"
      >
        <div class="flex items-center gap-2">
          <span class="text-xl">{{ getTypeIcon(type.id) }}</span>
          <span class="text-sm font-medium text-text-primary dark:text-text-primary-dark">
            {{ type.name }}
          </span>
        </div>
        <div class="text-xs text-text-secondary dark:text-text-secondary-dark line-clamp-2">
          {{ type.description }}
        </div>
      </button>
    </div>
    
    <!-- Empty state -->
    <div
      v-if="filteredTypes.length === 0 && !disabled"
      class="flex flex-col items-center justify-center py-8 text-text-secondary dark:text-text-secondary-dark"
    >
      <div class="text-2xl mb-2">🔍</div>
      <div class="text-sm">No types found</div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * TypeSelector component
 * 
 * Displays list of content types with search and selection
 */

import { ref, computed } from 'vue'
import type { ContentTypeMetadata } from '../../content-type-manager-cell/frontend/ContentTypeManagerCell'

interface Props {
  types: ContentTypeMetadata[]
  selectedTypeId: string | null
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false
})

defineEmits<{
  'select-type': [typeId: string]
}>()

// Search
const searchQuery = ref('')

// Filtered types based on search
const filteredTypes = computed(() => {
  if (!searchQuery.value) {
    return props.types
  }
  
  const query = searchQuery.value.toLowerCase()
  return props.types.filter(type =>
    type.name.toLowerCase().includes(query) ||
    type.description.toLowerCase().includes(query) ||
    type.id.toLowerCase().includes(query)
  )
})

/**
 * Get icon for content type
 */
function getTypeIcon(typeId: string): string {
  const iconMap: Record<string, string> = {
    'image-png': '🖼️',
    'image-jpg': '🖼️',
    'vector-svg': '🎨',
    '3d-glb': '🧊',
    '3d-obj': '🧊',
    'video-mp4': '🎬',
    'audio-mp3': '🎵'
  }
  return iconMap[typeId] || '📄'
}
</script>
