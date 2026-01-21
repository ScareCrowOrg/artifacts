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
  <div v-if="metadata" class="mt-6 bg-gray-800 p-4 rounded">
    <h3 class="text-lg font-semibold mb-2">Mesh Information</h3>
    
    <!-- Optimization Status Banner -->
    <div v-if="metadata.blenderOptimized !== undefined" class="mb-3 p-2 rounded text-sm">
      <div v-if="metadata.blenderOptimized" class="bg-emerald-900/30 border border-emerald-700/50 text-emerald-200">
        <div class="flex items-center gap-2">
          <span class="text-lg">✓</span>
          <div>
            <strong>Optimized Mesh</strong>
            <p class="text-xs opacity-75">Processed with Blender optimization + Draco compression</p>
          </div>
        </div>
      </div>
      <div v-else class="bg-amber-900/30 border border-amber-700/50 text-amber-200">
        <div class="flex items-center gap-2">
          <span class="text-lg">⚠</span>
          <div>
            <strong>Raw Mesh (Optimization Skipped)</strong>
            <p class="text-xs opacity-75">Blender optimization failed - delivered raw SF3D output</p>
            <p v-if="metadata.blenderError" class="text-xs mt-1 opacity-60">
              Reason: {{ metadata.blenderError }}
            </p>
          </div>
        </div>
      </div>
    </div>
    
    <div class="grid grid-cols-2 gap-2 text-sm">
      <div><strong>Vertices:</strong> {{ metadata.vertices?.toLocaleString() || 'N/A' }}</div>
      <div><strong>Faces:</strong> {{ metadata.faces?.toLocaleString() || 'N/A' }}</div>
      <div><strong>File Size:</strong> {{ metadata.fileSizeBytes ? (metadata.fileSizeBytes / 1024).toFixed(2) + ' KB' : 'N/A' }}</div>
      <div><strong>Format:</strong> {{ metadata.blenderOptimized ? 'GLB (optimized)' : 'OBJ (raw)' }}</div>
      <div><strong>Compression:</strong> {{ metadata.blenderOptimized ? 'Draco (enabled)' : 'None' }}</div>
      
      <!-- Processing Pipeline Status -->
      <div class="col-span-2 border-t border-gray-700 mt-2 pt-2">
        <strong class="block mb-1">Processing Pipeline:</strong>
        <div class="grid grid-cols-2 gap-2 text-xs">
          <div class="flex items-center gap-1">
            <span :class="metadata.sf3dCompleted ? 'text-green-400' : 'text-gray-500'">
              {{ metadata.sf3dCompleted ? '✓' : '○' }}
            </span>
            <span>SF3D Generation</span>
          </div>
          <div class="flex items-center gap-1">
            <span :class="metadata.blenderOptimized ? 'text-green-400' : 'text-amber-400'">
              {{ metadata.blenderOptimized ? '✓' : '○' }}
            </span>
            <span>Blender Optimization</span>
          </div>
        </div>
      </div>
      
      <!-- Processing Times -->
      <div v-if="metadata.sf3dTime" class="col-span-1"><strong>SF3D Time:</strong> {{ metadata.sf3dTime.toFixed(2) }}s</div>
      <div v-if="metadata.blenderTime" class="col-span-1"><strong>Blender Time:</strong> {{ metadata.blenderTime.toFixed(2) }}s</div>
      <div v-if="metadata.totalProcessingTime" class="col-span-2"><strong>Total Time:</strong> {{ metadata.totalProcessingTime.toFixed(2) }}s</div>
      <div v-if="metadata.generationTimeSeconds && !metadata.totalProcessingTime" class="col-span-2"><strong>Generation Time:</strong> {{ metadata.generationTimeSeconds.toFixed(2) }}s</div>
      
      <!-- Additional notes -->
      <div v-if="metadata.note || metadata.message" class="col-span-2 text-yellow-400 mt-2">
        <strong>Note:</strong> {{ metadata.note || metadata.message }}
      </div>
    </div>
  </div>
</template>
