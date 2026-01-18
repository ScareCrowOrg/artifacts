<script setup lang="ts">
/**
 * Mesh Metadata Display Component
 * 
 * Shows detailed information about the generated 3D mesh including
 * geometry stats, file size, and processing times.
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
    <div class="grid grid-cols-2 gap-2 text-sm">
      <div><strong>Vertices:</strong> {{ metadata.vertices?.toLocaleString() || 'N/A' }}</div>
      <div><strong>Faces:</strong> {{ metadata.faces?.toLocaleString() || 'N/A' }}</div>
      <div><strong>File Size:</strong> {{ metadata.fileSizeBytes ? (metadata.fileSizeBytes / 1024).toFixed(2) + ' KB' : 'N/A' }}</div>
      <div><strong>Compression:</strong> {{ metadata.compressionEnabled ? 'Enabled' : 'Disabled' }}</div>
      <div v-if="metadata.sf3dTime"><strong>SF3D Time:</strong> {{ metadata.sf3dTime.toFixed(2) }}s</div>
      <div v-if="metadata.blenderTime"><strong>Blender Time:</strong> {{ metadata.blenderTime.toFixed(2) }}s</div>
      <div v-if="metadata.totalProcessingTime"><strong>Total Time:</strong> {{ metadata.totalProcessingTime.toFixed(2) }}s</div>
      <div v-if="metadata.generationTimeSeconds && !metadata.totalProcessingTime"><strong>Generation Time:</strong> {{ metadata.generationTimeSeconds.toFixed(2) }}s</div>
      <div v-if="metadata.note" class="col-span-2 text-yellow-400 mt-2">
        <strong>Note:</strong> {{ metadata.note }}
      </div>
    </div>
  </div>
</template>
