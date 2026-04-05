/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-28",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<script setup lang="ts">
/**
 * Generation Mode Switcher Component
 * 
 * Allows users to switch between 3 generation modes:
 * - Cloud API (default): External API for mesh generation
 * - Local GPU (experimental): Local Redis/Windows Worker pipeline
 * - Manual Upload: Direct GLB file upload
 * 
 * @component
 */
import { computed } from 'vue'
import { createLogger } from '@/utils/logger'

const logger = createLogger('component:generation-mode-switcher')

type GenerationMode = 'cloud-api' | 'local-gpu' | 'manual-upload'

interface Props {
  modelValue: GenerationMode
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: GenerationMode): void
}>()

const modes: Array<{
  value: GenerationMode
  label: string
  description: string
  icon: string
  badge: string | null
}> = [
  {
    value: 'cloud-api',
    label: 'Cloud API',
    description: 'Fast generation via external API (default)',
    icon: '☁️',
    badge: 'Default'
  },
  {
    value: 'local-gpu',
    label: 'Local GPU',
    description: 'Local pipeline with Redis/Windows Worker',
    icon: '⚡',
    badge: 'Experimental'
  },
  {
    value: 'manual-upload',
    label: 'Manual Upload',
    description: 'Upload your own GLB file for preview',
    icon: '📁',
    badge: null
  }
]

const selectedMode = computed({
  get: () => props.modelValue,
  set: (value: GenerationMode) => {
    logger.info(`Generation mode changed to: ${value}`)
    emit('update:modelValue', value)
  }
})

const selectMode = (mode: GenerationMode) => {
  if (!props.disabled) {
    selectedMode.value = mode
  }
}

const isSelected = (mode: GenerationMode) => {
  return selectedMode.value === mode
}
</script>

<template>
  <div class="generation-mode-switcher">
    <label class="block text-sm font-medium mb-3 text-text-primary dark:text-text-primary-dark">
      Generation Mode
    </label>
    
    <div class="grid grid-cols-3 gap-2">
      <button
        v-for="mode in modes"
        :key="mode.value"
        type="button"
        :disabled="disabled"
        :class="[
          'mode-card relative p-4 rounded-lg border-2 transition-all duration-200',
          'flex flex-col items-start text-left',
          isSelected(mode.value)
            ? 'border-primary dark:border-primary-light bg-primary/10 dark:bg-primary-light/10'
            : 'border-border dark:border-border-dark bg-surface dark:bg-surface-dark hover:border-primary/50 dark:hover:border-primary-light/50',
          disabled && 'opacity-50 cursor-not-allowed'
        ]"
        @click="selectMode(mode.value)"
      >
        <!-- Badge -->
        <span
          v-if="mode.badge"
          :class="[
            'absolute top-2 right-2 px-2 py-0.5 text-xs font-semibold rounded',
            mode.badge === 'Default'
              ? 'bg-success dark:bg-success-light text-white'
              : 'bg-warning dark:bg-warning-light text-white'
          ]"
        >
          {{ mode.badge }}
        </span>

        <!-- Icon and Label -->
        <div class="flex items-center gap-2 mb-2">
          <span class="text-2xl">{{ mode.icon }}</span>
          <span class="font-semibold text-text-primary dark:text-text-primary-dark">
            {{ mode.label }}
          </span>
        </div>

        <!-- Description -->
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark">
          {{ mode.description }}
        </p>

        <!-- Selected Indicator -->
        <div
          v-if="isSelected(mode.value)"
          class="absolute bottom-2 right-2 w-5 h-5 rounded-full bg-primary dark:bg-primary-light flex items-center justify-center"
        >
          <svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
            <path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            />
          </svg>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.mode-card {
  min-height: 80px;
  position: relative;
  cursor: pointer;
}

.mode-card:disabled {
  cursor: not-allowed;
}
</style>
