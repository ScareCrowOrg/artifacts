<template>
  <div class="flex flex-col gap-3">
    <!-- Grid view -->
    <div
      v-if="viewMode === 'grid'"
      class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
    >
      <div
        v-for="asset in assets"
        :key="asset.id"
        class="flex flex-col gap-2 p-3 bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-md hover:border-primary dark:hover:border-primary-dark transition-colors group"
      >
        <!-- Preview placeholder -->
        <div class="w-full h-32 bg-surface-hover dark:bg-surface rounded flex items-center justify-center text-text-secondary dark:text-text-secondary-dark text-4xl">
          {{ getTypeIcon(asset.content_type_id) }}
        </div>
        
        <!-- Info -->
        <div class="flex flex-col gap-1">
          <div class="text-sm font-medium text-text-primary dark:text-text-primary-dark truncate" :title="asset.filename">
            {{ asset.filename }}
          </div>
          <div class="text-xs text-text-secondary dark:text-text-secondary-dark">
            {{ formatFileSize(asset.size_bytes) }}
          </div>
          <div v-if="asset.created_at" class="text-xs text-text-secondary dark:text-text-secondary-dark">
            {{ formatDate(asset.created_at) }}
          </div>
        </div>
        
        <!-- Actions (visible on hover) -->
        <div class="flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
          <AssetActions
            :disabled="disabled"
            @delete="$emit('delete-asset', asset.id)"
            @view="$emit('view-asset', asset.id)"
          />
        </div>
      </div>
    </div>
    
    <!-- List view -->
    <div v-else class="flex flex-col gap-2">
      <div
        v-for="asset in assets"
        :key="asset.id"
        class="flex items-center gap-3 p-3 bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-md hover:border-primary dark:hover:border-primary-dark transition-colors"
      >
        <div class="text-2xl">
          {{ getTypeIcon(asset.content_type_id) }}
        </div>
        
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium text-text-primary dark:text-text-primary-dark truncate">
            {{ asset.filename }}
          </div>
          <div class="text-xs text-text-secondary dark:text-text-secondary-dark">
            {{ formatFileSize(asset.size_bytes) }}
            <span v-if="asset.created_at"> • {{ formatDate(asset.created_at) }}</span>
          </div>
        </div>
        
        <AssetActions
          :disabled="disabled"
          @delete="$emit('delete-asset', asset.id)"
          @view="$emit('view-asset', asset.id)"
        />
      </div>
    </div>
    
    <!-- Empty state -->
    <div
      v-if="assets.length === 0 && !disabled"
      class="flex flex-col items-center justify-center py-12 text-text-secondary dark:text-text-secondary-dark"
    >
      <div class="text-4xl mb-2">📭</div>
      <div class="text-sm">No assets found</div>
      <div class="text-xs">Try selecting a different content type</div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * AssetGrid component
 * 
 * Displays assets in grid or list view
 */

import { type PropType } from 'vue'
import type { AssetItem } from '../ContentExplorerCell'
import AssetActions from './AssetActions.vue'

interface Props {
  assets: AssetItem[]
  viewMode?: 'grid' | 'list'
  disabled?: boolean
}

withDefaults(defineProps<Props>(), {
  viewMode: 'grid',
  disabled: false
})

defineEmits<{
  'delete-asset': [assetId: string]
  'view-asset': [assetId: string]
}>()

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

/**
 * Format file size in human-readable format
 */
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

/**
 * Format date in readable format
 */
function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return dateStr
  }
}
</script>
