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
/**
 * FileTreeNode Component for FileManagerCell
 * 
 * Displays a single file tree node with selection and expansion capabilities
 * Designed specifically for the FileManagerCell's tree view
 */
<template>
  <div class="select-none">
    <div
      :class="[
        'flex items-center gap-1 px-2 py-1 rounded transition-colors cursor-pointer',
        {
          'bg-primary-light/15 dark:bg-primary-dark/20 text-primary dark:text-primary-light font-medium': isSelected,
          'hover:bg-surface-hover dark:hover:bg-surface-hover-dark': !isSelected,
        },
      ]"
      @click="handleClick"
    >
      <!-- Expansion Toggle for Directories -->
      <button
        v-if="node.isDirectory"
        class="p-0 min-w-[20px] w-5 h-5 border-none bg-transparent hover:bg-surface-hover dark:hover:bg-surface-hover-dark rounded transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
        @click.stop="handleToggleExpanded"
      >
        <span class="text-xs block">{{ isExpanded ? '▼' : '▶' }}</span>
      </button>
      <span v-else class="w-5 flex-shrink-0"></span>

      <!-- File/Directory Icon -->
      <span class="text-sm flex-shrink-0">
        {{ node.isDirectory ? '📁' : '📄' }}
      </span>

      <!-- File/Directory Name -->
      <span class="text-sm flex-grow overflow-hidden text-ellipsis whitespace-nowrap">
        {{ node.name }}
      </span>

      <!-- File Size (for files only) -->
      <span
        v-if="!node.isDirectory && node.size !== undefined"
        class="text-xs text-text-secondary dark:text-text-secondary-dark ml-2"
      >
        {{ formatFileSize(node.size) }}
      </span>
    </div>

    <!-- Children (Recursive) -->
    <div v-if="node.isDirectory && isExpanded && node.children && node.children.length > 0" class="ml-6">
      <FileTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :selected-files="selectedFiles"
        :expanded-paths="expandedPaths"
        @toggle-selection="$emit('toggle-selection', $event)"
        @toggle-expanded="$emit('toggle-expanded', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FileTreeNode as FileTreeNodeType } from '../types'

/**
 * Props interface
 */
interface Props {
  /** The tree node to render */
  node: FileTreeNodeType
  /** Array of selected file paths */
  selectedFiles: string[]
  /** Set of expanded directory paths */
  expandedPaths: Set<string>
}

const props = defineProps<Props>()

/**
 * Emits
 */
const emit = defineEmits<{
  'toggle-selection': [path: string]
  'toggle-expanded': [path: string]
}>()

/**
 * Computed - Is this node expanded?
 */
const isExpanded = computed<boolean>(() => {
  return props.expandedPaths.has(props.node.path)
})

/**
 * Computed - Is this node selected?
 */
const isSelected = computed<boolean>(() => {
  return props.selectedFiles.includes(props.node.path)
})

/**
 * Handle click on node
 */
function handleClick(): void {
  // Only allow selection of files, not directories
  if (!props.node.isDirectory) {
    emit('toggle-selection', props.node.path)
  }
}

/**
 * Handle toggle expanded for directories
 */
function handleToggleExpanded(): void {
  if (props.node.isDirectory) {
    emit('toggle-expanded', props.node.path)
  }
}

/**
 * Format file size to human-readable format
 */
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 10) / 10 + ' ' + sizes[i]
}
</script>


