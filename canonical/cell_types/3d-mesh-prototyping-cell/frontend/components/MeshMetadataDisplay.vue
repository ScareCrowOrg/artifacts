/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-22",
 *   "theme_compliance": 98,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<script setup lang="ts">
/**
 * Mesh Metadata Display Component
 * 
 * Shows detailed information about the generated 3D mesh including
 * geometry stats, file size, processing times, and optimization status.
 * 
 * @component
 */
const props = defineProps<{
  metadata: Record<string, any> | null
}>()
</script>

<template>
  <div v-if="metadata" class="mt-6 bg-surface dark:bg-surface-dark border border-border dark:border-border-dark p-4 rounded">
    <h3 class="text-lg font-semibold mb-2 text-text-primary dark:text-text-primary-dark">{{ $t('artifacts.meshPrototypingCell.meshMetadata.title') }}</h3>

    <!-- Optimization Status Banner -->
    <div v-if="metadata.blenderOptimized !== undefined" class="mb-3 p-2 rounded text-sm">
      <div v-if="metadata.blenderOptimized" class="bg-success/10 dark:bg-success/20 border border-success dark:border-success-light text-success dark:text-success-light">
        <div class="flex items-center gap-2">
          <span class="text-lg">✓</span>
          <div>
            <strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.optimizedMesh') }}</strong>
            <p class="text-xs opacity-75">{{ $t('artifacts.meshPrototypingCell.meshMetadata.optimizedDescription') }}</p>
          </div>
        </div>
      </div>
      <div v-else class="bg-warning/10 dark:bg-warning/20 border border-warning dark:border-warning-light text-warning dark:text-warning-light">
        <div class="flex items-center gap-2">
          <span class="text-lg">⚠</span>
          <div>
            <strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.rawMesh') }}</strong>
            <p class="text-xs opacity-75">{{ $t('artifacts.meshPrototypingCell.meshMetadata.rawDescription') }}</p>
            <p v-if="metadata.blenderError" class="text-xs mt-1 opacity-60">
              {{ $t('artifacts.meshPrototypingCell.meshMetadata.reason', { reason: metadata.blenderError }) }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-2 text-sm text-text-primary dark:text-text-primary-dark">
      <div><strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.vertices') }}</strong> {{ metadata.vertices?.toLocaleString() || $t('artifacts.meshPrototypingCell.meshMetadata.notApplicable') }}</div>
      <div><strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.faces') }}</strong> {{ metadata.faces?.toLocaleString() || $t('artifacts.meshPrototypingCell.meshMetadata.notApplicable') }}</div>
      <div><strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.fileSize') }}</strong> {{ metadata.fileSizeBytes ? (metadata.fileSizeBytes / 1024).toFixed(2) + ' KB' : $t('artifacts.meshPrototypingCell.meshMetadata.notApplicable') }}</div>
      <div><strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.format') }}</strong> {{ metadata.blenderOptimized ? $t('artifacts.meshPrototypingCell.meshMetadata.formatOptimized') : $t('artifacts.meshPrototypingCell.meshMetadata.formatRaw') }}</div>
      <div><strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.compression') }}</strong> {{ metadata.blenderOptimized ? $t('artifacts.meshPrototypingCell.meshMetadata.compressionDraco') : $t('artifacts.meshPrototypingCell.meshMetadata.compressionNone') }}</div>

      <!-- Processing Pipeline Status -->
      <div class="col-span-2 border-t border-border dark:border-border-dark mt-2 pt-2">
        <strong class="block mb-1">{{ $t('artifacts.meshPrototypingCell.meshMetadata.pipeline') }}</strong>
        <div class="grid grid-cols-2 gap-2 text-xs">
          <div class="flex items-center gap-1">
            <span :class="metadata.sf3dCompleted ? 'text-success dark:text-success-light' : 'text-text-secondary dark:text-text-secondary-dark'">
              {{ metadata.sf3dCompleted ? '✓' : '○' }}
            </span>
            <span>{{ $t('artifacts.meshPrototypingCell.meshMetadata.pipelineSf3d') }}</span>
          </div>
          <div class="flex items-center gap-1">
            <span :class="metadata.blenderOptimized ? 'text-success dark:text-success-light' : 'text-warning dark:text-warning-light'">
              {{ metadata.blenderOptimized ? '✓' : '○' }}
            </span>
            <span>{{ $t('artifacts.meshPrototypingCell.meshMetadata.pipelineBlender') }}</span>
          </div>
        </div>
      </div>

      <!-- Processing Times -->
      <div v-if="metadata.sf3dTime" class="col-span-1"><strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.pipelineSf3d') }}:</strong> {{ metadata.sf3dTime.toFixed(2) }}s</div>
      <div v-if="metadata.blenderTime" class="col-span-1"><strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.pipelineBlender') }}:</strong> {{ metadata.blenderTime.toFixed(2) }}s</div>
      <div v-if="metadata.totalProcessingTime" class="col-span-2"><strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.totalTime') }}:</strong> {{ metadata.totalProcessingTime.toFixed(2) }}s</div>
      <div v-if="metadata.generationTimeSeconds && !metadata.totalProcessingTime" class="col-span-2"><strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.generationTime') }}:</strong> {{ metadata.generationTimeSeconds.toFixed(2) }}s</div>

      <!-- Additional notes -->
      <div v-if="metadata.note || metadata.message" class="col-span-2 text-warning dark:text-warning-light mt-2">
        <strong>{{ $t('artifacts.meshPrototypingCell.meshMetadata.noteLabel') }}:</strong> {{ metadata.note || metadata.message }}
      </div>
    </div>
  </div>
</template>
