/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-02",
 *   "theme_compliance": 90,
 *   "theme_status": "good",
 *   "theme_issues": 1,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <div class="quick-actions bg-surface border border-border rounded-lg p-4">
    <h3 class="text-sm font-semibold mb-3 text-foreground">Quick Actions</h3>
    
    <div class="actions-grid grid grid-cols-3 gap-3">
      <button
        v-for="action in availableActions"
        :key="action.id"
        @click="handleAction(action.id)"
        class="action-button"
        :disabled="isActionDisabled(action.id)"
      >
        <div class="flex flex-col items-center justify-center gap-2">
          <component 
            :is="getActionIcon(action.icon)" 
            class="w-6 h-6"
          />
          <span class="text-xs font-medium text-center">
            {{ action.label }}
          </span>
        </div>
      </button>
    </div>
    
    <!-- Action confirmation modal (if needed) -->
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div 
        v-if="showConfirmation"
        class="confirmation-overlay fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        @click.self="cancelAction"
      >
        <Transition
          enter-active-class="transition-all duration-200"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="transition-all duration-200"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div v-if="showConfirmation" class="confirmation-dialog bg-surface border border-border rounded-lg p-6 max-w-md shadow-2xl">
            <h4 class="text-lg font-semibold mb-2">Confirm Action</h4>
            <p class="text-sm text-muted-foreground mb-4">
              Are you sure you want to {{ pendingAction?.label.toLowerCase() }}?
            </p>
            
            <div class="flex gap-2 justify-end">
              <button
                @click="cancelAction"
                class="btn btn-sm btn-secondary"
              >
                Cancel
              </button>
              <button
                @click="confirmAction"
                class="btn btn-sm btn-primary"
              >
                Confirm
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, type PropType } from 'vue'

// Simple SVG icon components (no external dependencies)
const TrashIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>' }
const ArrowPathIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>' }
const ArrowDownTrayIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>' }
const Cog6ToothIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>' }
const DocumentTextIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>' }
const BellIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" /></svg>' }

interface QuickAction {
  id: string
  label: string
  icon: string
  requiresConfirmation?: boolean
}

const props = defineProps({
  availableActions: {
    type: Array as PropType<QuickAction[]>,
    required: true
  }
})

const emit = defineEmits<{
  action: [actionId: string]
}>()

const showConfirmation = ref(false)
const pendingAction = ref<QuickAction | null>(null)
const disabledActions = ref<string[]>([])

function getActionIcon(iconName: string) {
  const icons: Record<string, any> = {
    trash: TrashIcon,
    refresh: ArrowPathIcon,
    download: ArrowDownTrayIcon,
    settings: Cog6ToothIcon,
    document: DocumentTextIcon,
    bell: BellIcon
  }
  return icons[iconName] || Cog6ToothIcon
}

function isActionDisabled(actionId: string): boolean {
  return disabledActions.value.includes(actionId)
}

function handleAction(actionId: string): void {
  const action = props.availableActions.find(a => a.id === actionId)
  
  if (!action) return
  
  if (action.requiresConfirmation) {
    pendingAction.value = action
    showConfirmation.value = true
  } else {
    executeAction(actionId)
  }
}

function confirmAction(): void {
  if (pendingAction.value) {
    executeAction(pendingAction.value.id)
  }
  cancelAction()
}

function cancelAction(): void {
  showConfirmation.value = false
  pendingAction.value = null
}

function executeAction(actionId: string): void {
  // Temporarily disable the action button
  disabledActions.value.push(actionId)
  
  emit('action', actionId)
  
  // Re-enable after 2 seconds
  setTimeout(() => {
    disabledActions.value = disabledActions.value.filter(id => id !== actionId)
  }, 2000)
}
</script>

<style scoped>
.quick-actions {
  @apply transition-all;
}

.actions-grid {
  @apply gap-3;
}

.action-button {
  @apply bg-background border border-border rounded-lg p-4 transition-all;
  @apply hover:bg-primary/10 hover:border-primary/30 hover:shadow-md;
  @apply active:scale-95;
  @apply disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-background;
}

.action-button:not(:disabled):hover {
  @apply transform scale-105;
}
</style>
