/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-11",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues": 0,
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-28",
 *   "console_calls_found": 26,
 *   "console_calls_migrated": 26,
 *   "migration_rate": 100,
 *   "logger_namespace": "chat:settings",
 *   "validation_status": "excellent"
 * }
 */
<template>
  <transition name="settings-slide">
    <div
      v-if="visible"
      class="border-t max-h-[600px] overflow-y-auto settings-panel"
      data-testid="chat-settings-panel"
    >
      <div class="p-4 space-y-3">
        <!-- Model Selection -->
        <div class="flex items-center gap-4">
          <div class="flex items-center gap-2 flex-1">
            <label
              for="model-select"
              class="font-medium whitespace-nowrap text-sm"
            >
              {{ $t('chatSettingsPanel.modelLabel') }}
            </label>
            <select
              id="model-select"
              :value="chat.selectedModel.value"
              :disabled="chat.isLoading.value || chat.isLoadingModels.value"
              class="flex-1 px-2 py-1 border rounded text-sm model-select"
              data-testid="model-select"
              @change="handleModelChange"
            >
              <option v-if="chat.isLoadingModels.value" disabled value="">
                {{ $t('chatSettingsPanel.loadingModels') }}
              </option>
              <optgroup
                v-if="
                  !chat.isLoadingModels.value &&
                  chat.localModels.value.length > 0
                "
                :label="$t('chatSettingsPanel.localModelsGroup')"
              >
                <option
                  v-for="model in chat.localModels.value"
                  :key="model.value"
                  :value="model.value"
                >
                  {{ model.label }}
                </option>
              </optgroup>
              <optgroup
                v-if="
                  !chat.isLoadingModels.value &&
                  chat.externalModels.value.length > 0
                "
                :label="$t('chatSettingsPanel.externalModelsGroup')"
              >
                <option
                  v-for="model in chat.externalModels.value"
                  :key="model.value"
                  :value="model.value"
                >
                  {{ model.label }}
                </option>
              </optgroup>
              <option
                v-if="
                  !chat.isLoadingModels.value &&
                  chat.availableModels.value.length === 0
                "
                disabled
                value=""
              >
                {{ $t('chatSettingsPanel.noModelsAvailable') }}
              </option>
            </select>
          </div>
        </div>

        <!-- AgenteLab Warm-up Configuration -->
        <div class="flex items-center gap-4">
          <div class="flex items-center gap-2 flex-1">
            <label
              for="warmup-select"
              class="font-medium whitespace-nowrap text-sm"
            >
              {{ $t('chatSettingsPanel.warmupLabel') }}
            </label>
            <select
              id="warmup-select"
              v-model="warmupSelection"
              :disabled="chat.isLoading.value || isLoadingWarmup"
              class="flex-1 px-2 py-1 border rounded text-sm warmup-select"
              data-testid="warmup-select"
              @change="handleWarmupChange"
            >
              <option value="">
                {{ $t('chatSettingsPanel.warmupDefault') }}
              </option>
              <option v-if="isLoadingWarmup" disabled value="">
                {{ $t('chatSettingsPanel.warmupLoading') }}
              </option>
              <optgroup
                v-if="!isLoadingWarmup && personas.length > 0"
                :label="$t('chatSettingsPanel.warmupPersonasGroup')"
              >
                <option
                  v-for="persona in personas"
                  :key="`persona-${persona.id}`"
                  :value="`persona:${persona.id}`"
                >
                  {{ persona.name }}
                </option>
              </optgroup>
              <optgroup
                v-if="!isLoadingWarmup && warmupFiles.length > 0"
                :label="$t('chatSettingsPanel.warmupFilesGroup')"
              >
                <option
                  v-for="file in warmupFiles"
                  :key="`file-${file.filename}`"
                  :value="`file:${file.filename}`"
                >
                  {{ file.filename }}
                </option>
              </optgroup>
            </select>
          </div>
        </div>

        <!-- AgenteLab Action Links Reference -->
        <div class="flex items-center gap-4">
          <div class="flex items-center gap-2 flex-1">
            <label
              for="actions-select"
              class="font-medium whitespace-nowrap text-sm"
            >
              {{ $t('chatSettingsPanel.actionsLabel') }}
            </label>
            <select
              id="actions-select"
              v-model="selectedAction"
              :disabled="chat.isLoading.value || actionDiscovery.isLoading.value"
              class="flex-1 px-2 py-1 border rounded text-sm actions-select"
              data-testid="actions-select"
              @change="handleActionChange"
            >
              <option value="">
                {{ $t('chatSettingsPanel.actionsDefault') }}
              </option>
              <option v-if="actionDiscovery.isLoading.value" disabled value="">
                {{ $t('chatSettingsPanel.actionsLoading') }}
              </option>
              <option
                v-for="action in allActions"
                v-if="!actionDiscovery.isLoading.value"
                :key="action.filename"
                :value="action.filename"
              >
                {{ action.action_name }}
              </option>
            </select>
          </div>
        </div>

        <!-- Agent Mode Toggle (MVP 4.1) -->
        <div
          class="flex items-center gap-2 border rounded px-3 py-2 agent-mode-toggle"
          data-testid="agent-mode-toggle"
        >
          <input
            id="agent-mode"
            type="checkbox"
            :checked="isAgentModeEnabled"
            :disabled="chat.isLoading.value"
            class="w-4 h-4 cursor-pointer"
            @change="handleAgentModeToggle"
          />
          <label for="agent-mode" class="text-sm cursor-pointer font-medium">
            ⚡ {{ $t('chatSettingsPanel.agentModeLabel') }}
          </label>
        </div>

        <!-- Intention Classification Toggle -->
        <div
          class="flex items-center gap-2 border rounded px-3 py-2 intention-toggle"
        >
          <input
            id="intention-classification"
            type="checkbox"
            :checked="chat.enableIntentionClassification.value"
            :disabled="chat.isLoading.value"
            class="w-4 h-4 cursor-pointer"
            @change="handleIntentionClassificationChange"
          />
          <label for="intention-classification" class="text-sm cursor-pointer">
            {{ $t('chatSettingsPanel.intentionToggleLabel') }}
          </label>
        </div>

        <!-- Collection Selector -->
        <CollectionSelector
          v-model="internalSelectedCollections"
          :available-collections="chat.availableCollections.value"
          :disabled="chat.isLoading.value"
        />

        <!-- Attachments Manager -->
        <div
          class="p-3 border rounded-md attachments-container"
          data-testid="attachments-container"
        >
          <div class="flex items-center gap-2 mb-2 text-sm">
            <span class="font-semibold attachments-title">
              {{ $t('chatSettingsPanel.attachmentsTitle') }} ({{ chat.attachments.value.length }}/{{
                chat.maxAttachments
              }})
            </span>
            <span
              :class="[
                'text-xs',
                {
                  'text-warning font-medium': chat.attachmentsWarning.value,
                  'text-error font-bold': chat.attachmentsSizeExceeded.value,
                },
              ]"
              class="attachments-size"
            >
              {{ formatBytes(chat.totalAttachmentsSize.value) }} /
              {{ formatBytes(chat.attachmentsTotalMaxSize) }}
            </span>
            <button
              class="ml-auto px-2 py-0.5 bg-transparent border rounded text-xs transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed btn-clear-attachments"
              :title="$t('chatSettingsPanel.clearAttachmentsTooltip')"
              :disabled="
                chat.isLoading.value || chat.attachments.value.length === 0
              "
              @click="chat.clearAttachments()"
            >
              🗑️
            </button>
          </div>

          <div class="flex flex-col gap-1">
            <div
              v-if="chat.attachments.value.length === 0"
              class="text-xs italic px-2 py-1 empty-attachments"
            >
              {{ $t('chatSettingsPanel.noAttachmentsYet') }}
            </div>
            <div
              v-for="attachment in chat.attachments.value"
              :key="attachment.id"
            >
              <div
                class="flex items-center gap-2 px-2 py-1 border rounded text-sm attachment-item"
                :data-testid="`attachment-${attachment.id}`"
              >
                <span class="text-base flex-shrink-0">📄</span>
                <div class="flex-1 min-w-0">
                  <div
                    class="whitespace-nowrap overflow-hidden text-ellipsis attachment-name"
                    :title="attachment.path || attachment.filename"
                  >
                    {{ attachment.filename }}
                  </div>
                  <div
                    v-if="attachment.path"
                    class="text-xs text-opacity-70 whitespace-nowrap overflow-hidden text-ellipsis attachment-path"
                    :title="attachment.path"
                  >
                    {{ attachment.path }}
                  </div>
                </div>
                <span class="text-xs flex-shrink-0 attachment-size">
                  {{ formatBytes(attachment.size) }}
                </span>
                <button
                  class="px-1.5 py-0.5 bg-transparent border border-transparent rounded text-sm transition-all duration-200 flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed btn-view-attachment"
                  :title="$t('chatSettingsPanel.viewContentTooltip')"
                  :disabled="chat.isLoading.value"
                  @click="openContentPreview(attachment)"
                >
                  🔍
                </button>
                <button
                  class="px-1.5 py-0.5 bg-transparent border border-transparent rounded text-sm transition-all duration-200 flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed btn-remove-attachment"
                  :title="$t('chatSettingsPanel.removeAttachmentTooltip')"
                  :disabled="chat.isLoading.value"
                  @click="chat.removeAttachment(attachment.filename)"
                >
                  ✕
                </button>
              </div>
            </div>
          </div>

          <div
            v-if="chat.attachmentsSizeExceeded.value"
            class="mt-2 px-2 py-1 border rounded text-xs font-medium attachments-error"
          >
            {{ $t('chatSettingsPanel.attachmentsSizeExceeded') }}
          </div>
        </div>
      </div>
    </div>
  </transition>

  <!-- Content Preview Modal -->
  <Teleport to="body">
    <transition name="modal-fade">
      <div
        v-if="previewVisible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-overlay"
        @click.self="closeContentPreview"
      >
        <div
          class="w-full max-w-4xl max-h-[80vh] flex flex-col rounded-lg shadow-xl modal-container"
          @click.stop
        >
          <div class="flex items-center justify-between p-4 border-b modal-header">
            <h3 class="text-lg font-semibold modal-title">
              {{ $t('chatSettingsPanel.contentPreviewTitle') }}: {{ previewAttachment?.filename }}
            </h3>
            <button
              class="px-3 py-1 rounded transition-all duration-200 btn-close-modal"
              @click="closeContentPreview"
            >
              {{ $t('chatSettingsPanel.closePreview') }}
            </button>
          </div>
          <div
            v-if="previewAttachment?.path"
            class="px-4 py-2 text-sm border-b modal-path"
          >
            <span class="font-medium">Path:</span> {{ previewAttachment.path }}
          </div>
          <div class="flex-1 overflow-auto p-4 modal-content">
            <pre class="text-sm whitespace-pre-wrap break-words content-pre">{{ previewAttachment?.content }}</pre>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatBytes } from '../../config/chatLimits.js'
import CollectionSelector from './CollectionSelector.vue'
import { useActionDiscovery } from '../../composables/useActionDiscovery.ts'
import { useChatStore } from '../../stores/chat'
import apiService from '@/services/apiService'
import { createLogger } from '@/utils/logger'

const log = createLogger('chat:settings')

const { t: $t } = useI18n()

// Access chat store for Agent Mode state (MVP 4.1)
const chatStore = useChatStore()

const props = defineProps({
  visible: {
    type: Boolean,
    required: true,
  },
  chat: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['update:selected-model', 'update:enable-intention-classification', 'update:selected-collections'])

const internalSelectedCollections = ref(props.chat.selectedCollections.value)

// Content preview state
const previewVisible = ref(false)
const previewAttachment = ref(null)

// Warm-up configuration state
const selectedWarmupPersona = ref('')
const selectedWarmupFile = ref('')
const personas = ref([])
const warmupFiles = ref([])
const isLoadingWarmup = ref(false)
const warmupError = ref(null)

// Action Links configuration state using discovery API
const selectedAction = ref('')
const actionDiscovery = useActionDiscovery()
const discoveredActions = ref([])

// All actions use JSON syntax - no need for type-based grouping
// Map discovered actions to the format expected by the template
const allActions = computed(() => {
  return discoveredActions.value.map(action => ({
    filename: `${action.name}.yml`,
    action_name: action.metadata?.action_name || action.name,
    description: action.description,
    labels: action.metadata?.labels || []
  }))
})
  
// Computed property for the combined selection value
const warmupSelection = computed({
  get() {
    if (selectedWarmupPersona.value) {
      return `persona:${selectedWarmupPersona.value}`
    } else if (selectedWarmupFile.value) {
      return `file:${selectedWarmupFile.value}`
    }
    return ''
  },
  set(_value) {
    // This will be handled by handleWarmupChange
    // We keep this setter to avoid Vue warnings
     
  }
})

// Load warm-up personas and files on mount
onMounted(async () => {
  await loadWarmupConfiguration()
  await loadActionFilesConfiguration()
})

async function loadWarmupConfiguration() {
  isLoadingWarmup.value = true
  warmupError.value = null
  
  try {
    // Load personas
    const personasResponse = await apiService.fetch('/api/config/agentlab/personas')
    if (personasResponse.ok) {
      const data = await personasResponse.json()
      personas.value = data.personas || []
    } else {
      const errorText = await personasResponse.text()
      log.error('Failed to load personas', personasResponse.status, errorText)
      warmupError.value = `Failed to load personas: ${personasResponse.statusText}`
    }
    
    // Load available files
    const filesResponse = await apiService.fetch('/api/config/agentlab/warm-up-files')
    if (filesResponse.ok) {
      warmupFiles.value = await filesResponse.json()
    } else {
      const errorText = await filesResponse.text()
      log.error('Failed to load warm-up files', filesResponse.status, errorText)
      warmupError.value = `Failed to load warm-up files: ${filesResponse.statusText}`
    }
  } catch (error) {
    log.error('Error loading warm-up configuration', error)
    warmupError.value = error.message || 'Unknown error loading warm-up configuration'
  } finally {
    isLoadingWarmup.value = false
  }
}

async function handleWarmupChange(event) {
  const selection = event.target.value
  
  if (!selection) {
    // Clear warm-up files from attachments
    clearWarmupAttachments()
    selectedWarmupPersona.value = ''
    selectedWarmupFile.value = ''
    return
  }
  
  try {
    // Clear previous warm-up files
    clearWarmupAttachments()
    
    // Check if selection is a persona or individual file
    if (selection.startsWith('persona:')) {
      const personaId = selection.substring(8) // Remove 'persona:' prefix
      const persona = personas.value.find(p => p.id === personaId)
      
      if (!persona || !persona.files) {
        return
      }
      
      // Update state
      selectedWarmupPersona.value = personaId
      selectedWarmupFile.value = ''
      
      // Load and attach files for selected persona
      for (const filename of persona.files) {
        const fileInfo = warmupFiles.value.find(f => f.filename === filename)
        if (fileInfo) {
          await attachWarmupFile(fileInfo)
        }
      }
    } else if (selection.startsWith('file:')) {
      const filename = selection.substring(5) // Remove 'file:' prefix
      const fileInfo = warmupFiles.value.find(f => f.filename === filename)
      
      if (!fileInfo) {
        return
      }
      
      // Update state
      selectedWarmupPersona.value = ''
      selectedWarmupFile.value = filename
      
      // Attach the single selected file
      await attachWarmupFile(fileInfo)
    }
  } catch (error) {
    log.error('Error attaching warm-up files', error)
  }
}

function clearWarmupAttachments() {
  // Remove all attachments with warmup flag
  const warmupAttachments = props.chat.attachments.value.filter(
    att => att.isWarmup
  )
  
  // Remove each warmup attachment using the provided method
  warmupAttachments.forEach(att => {
    props.chat.removeAttachment(att.filename)
  })
}

async function attachWarmupFile(fileInfo) {
  try {
    // Read file content using correct endpoint
    const response = await apiService.fetch(`/api/files/load?path=${encodeURIComponent(fileInfo.path)}`)
    if (!response.ok) {
      throw new Error(`Failed to read file: ${fileInfo.filename}`)
    }
    
    const data = await response.json()
    
    // Use the chat composable's addAttachment method
    // The method returns true if successful, false otherwise
    const success = props.chat.addAttachment(
      fileInfo.filename,
      data.content,
      'yaml',
      fileInfo.path
    )
    
    if (success) {
      // Mark the attachment as warmup by finding it and adding the flag
      // This happens after addAttachment has created the attachment object
      const addedAttachment = props.chat.attachments.value.find(
        att => att.filename === fileInfo.filename && att.path === fileInfo.path
      )
      if (addedAttachment) {
        addedAttachment.isWarmup = true
      }
    } else {
      log.warn(`Failed to attach warm-up file ${fileInfo.filename}`)
    }
  } catch (error) {
    log.error(`Error attaching warm-up file ${fileInfo.filename}`, error)
  }
}

async function loadActionFilesConfiguration() {
  // DEBUG LOG: Entry point
  log.debug('loadActionFilesConfiguration() called from ChatSettingsPanel')
  log.debug('actionDiscovery composable state', {
    isLoading: actionDiscovery.isLoading.value,
    hasCache: actionDiscovery.hasCache.value,
    lastError: actionDiscovery.lastError.value
  })
  
  try {
    // Use action discovery API to load all actions
    log.debug('Calling actionDiscovery.getAllActionsFlattened()...')
    const actions = await actionDiscovery.getAllActionsFlattened()
    
    // DEBUG LOG: Result
    log.debug('getAllActionsFlattened() returned', {
      type: typeof actions,
      isArray: Array.isArray(actions),
      length: actions ? actions.length : 'null'
    })
    if (actions && actions.length > 0) {
      log.debug('Actions details', {
        firstAction: actions[0],
        allActionNames: actions.map(a => a.name)
      })
    }
    
    discoveredActions.value = actions
    
    // DEBUG LOG: State after assignment
    log.debug('discoveredActions.value set to', discoveredActions.value.length, 'actions')
  } catch (error) {
    log.error('Error in loadActionFilesConfiguration', error)
    log.error('Error stack', error.stack)
    log.error('Error loading action files via discovery', error)
    // Fallback to empty array
    discoveredActions.value = []
    log.debug('Fallback: discoveredActions.value set to empty array')
  }
}

async function handleActionChange(event) {
  const filename = event.target.value
  
  if (!filename) {
    // Clear action file attachments if deselecting
    clearActionAttachments()
    return
  }
  
  // Extract action name from filename (remove .yml extension)
  const actionName = filename.replace(/\.ya?ml$/, '')
  const action = discoveredActions.value.find(a => a.name === actionName)
  
  if (!action) {
    return
  }
  
  try {
    // Clear previous action file attachments
    clearActionAttachments()
    
    // Load and attach the selected action file
    await attachActionFile(action)
  } catch (error) {
    log.error('Error attaching action file', error)
  }
}

function clearActionAttachments() {
  // Remove all attachments with isActionRef flag
  const actionAttachments = props.chat.attachments.value.filter(
    att => att.isActionRef
  )
  
  // Remove each action attachment using the provided method
  actionAttachments.forEach(att => {
    props.chat.removeAttachment(att.filename)
  })
}

async function attachActionFile(action) {
  try {
    // Get the full action details including syntax and examples
    const primaryLabel = action.primaryLabel || action.allLabels[0]
    const actionDetails = await actionDiscovery.discoverAction(primaryLabel, action.name)
    
    if (!actionDetails) {
      throw new Error(`Failed to load action details: ${action.name}`)
    }
    
    // Format action as YAML content for attachment
    const yamlContent = formatActionAsYAML(actionDetails)
    const filename = `${action.name}.yml`
    
    // Use the chat composable's addAttachment method
    const success = props.chat.addAttachment(
      filename,
      yamlContent,
      'yaml',
      `docs/official/agents/actions/${filename}`
    )
    
    if (success) {
      // Mark the attachment as action reference by finding it and adding the flag
      const addedAttachment = props.chat.attachments.value.find(
        att => att.filename === filename
      )
      if (addedAttachment) {
        addedAttachment.isActionRef = true
      }
    } else {
      log.warn(`Failed to attach action file ${filename}`)
    }
  } catch (error) {
    log.error(`Error attaching action file ${action.name}`, error)
  }
}

/**
 * Format action details as YAML content
 * 
 * @param {Object} action - Action details from discovery API
 * @returns {string} YAML formatted content
 */
function formatActionAsYAML(action) {
  const lines = ['---']
  
  // Metadata
  lines.push('metadata:')
  lines.push(`  action_name: "${action.metadata.action_name}"`)
  lines.push(`  action_type: "${action.metadata.action_type}"`)
  lines.push(`  version: "${action.metadata.version}"`)
  lines.push(`  status: "${action.metadata.status}"`)
  
  if (action.metadata.labels && action.metadata.labels.length > 0) {
    lines.push('  labels:')
    action.metadata.labels.forEach(label => {
      lines.push(`    - ${label}`)
    })
  }
  
  // Description
  lines.push('')
  lines.push('description: |')
  if (action.description) {
    action.description.split('\n').forEach(line => {
      lines.push(`  ${line}`)
    })
  }
  
  // Syntax
  if (action.syntax) {
    lines.push('')
    lines.push('syntax: |')
    action.syntax.split('\n').forEach(line => {
      lines.push(`  ${line}`)
    })
  }
  
  // Parameters
  if (action.parameters && action.parameters.length > 0) {
    lines.push('')
    const requiredFields = action.parameters.filter(p => p.required)
    const optionalFields = action.parameters.filter(p => !p.required)
    
    if (requiredFields.length > 0) {
      lines.push('required_fields:')
      requiredFields.forEach(param => {
        lines.push(`  - name: "${param.name}"`)
        lines.push(`    type: "${param.type}"`)
        if (param.description) {
          lines.push(`    description: "${param.description}"`)
        }
      })
    }
    
    if (optionalFields.length > 0) {
      lines.push('')
      lines.push('optional_fields:')
      optionalFields.forEach(param => {
        lines.push(`  - name: "${param.name}"`)
        lines.push(`    type: "${param.type}"`)
        if (param.default !== null && param.default !== undefined) {
          lines.push(`    default: ${JSON.stringify(param.default)}`)
        }
        if (param.description) {
          lines.push(`    description: "${param.description}"`)
        }
      })
    }
  }
  
  // Examples
  if (action.examples && action.examples.length > 0) {
    lines.push('')
    lines.push('examples:')
    action.examples.forEach(example => {
      lines.push(`  - name: "${example.name || 'Example'}"`)
      if (example.description) {
        lines.push(`    description: "${example.description}"`)
      }
    })
  }
  
  // Best practices
  if (action.best_practices && action.best_practices.length > 0) {
    lines.push('')
    lines.push('best_practices:')
    action.best_practices.forEach(practice => {
      lines.push(`  - "${practice}"`)
    })
  }
  
  // Tips
  if (action.tips && action.tips.length > 0) {
    lines.push('')
    lines.push('tips:')
    action.tips.forEach(tip => {
      lines.push(`  - "${tip}"`)
    })
  }
  
  return lines.join('\n')
}

// Sync internal collections with prop changes
watch(
  () => props.chat.selectedCollections.value,
  (newVal) => {
    internalSelectedCollections.value = newVal
  },
)

// Emit update event instead of mutating prop
watch(internalSelectedCollections, (newVal) => {
  emit('update:selected-collections', newVal)
})

// Agent Mode computed property (MVP 4.1)
const isAgentModeEnabled = computed(() => chatStore.isAgentMode)

// Agent Mode toggle handler (MVP 4.1)
function handleAgentModeToggle() {
  chatStore.toggleAgentMode()
  log.info('Agent Mode toggled', { enabled: chatStore.isAgentMode })
}

// Handlers for direct mutations
function handleModelChange(event) {
  emit('update:selected-model', event.target.value)
}

function handleIntentionClassificationChange(event) {
  emit('update:enable-intention-classification', event.target.checked)
}

// Content preview handlers
function openContentPreview(attachment) {
  previewAttachment.value = attachment
  previewVisible.value = true
}

function closeContentPreview() {
  previewVisible.value = false
  setTimeout(() => {
    previewAttachment.value = null
  }, 300)
}
</script>

<style scoped>
.settings-panel {
  background: var(--color-surface);
  border-color: var(--color-border);
}

.model-select {
  background: var(--color-surface);
  color: var(--color-text-primary);
  border-color: var(--color-border);
}

.warmup-select {
  background: var(--color-surface);
  color: var(--color-text-primary);
  border-color: var(--color-border);
}

.actions-select {
  background: var(--color-surface);
  color: var(--color-text-primary);
  border-color: var(--color-border);
}

.agent-mode-toggle {
  background: color-mix(in srgb, rgb(251, 191, 36) 15%, transparent);
  border-color: color-mix(in srgb, rgb(251, 191, 36) 30%, transparent);
  box-shadow: 0 0 8px color-mix(in srgb, rgb(251, 191, 36) 20%, transparent);
}

.agent-mode-toggle:hover {
  background: color-mix(in srgb, rgb(251, 191, 36) 25%, transparent);
  border-color: rgb(251, 191, 36);
}

.intention-toggle {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  border-color: color-mix(in srgb, var(--color-primary) 10%, transparent);
}

.attachments-container {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  border-color: color-mix(in srgb, var(--color-primary) 10%, transparent);
}

.attachments-title {
  color: var(--color-text-primary);
}

.attachments-size {
  color: var(--color-text-tertiary);
}

.btn-clear-attachments {
  border-color: var(--color-border);
}

.btn-clear-attachments:hover {
  background: color-mix(in srgb, var(--color-error) 10%, transparent);
  border-color: var(--color-error);
}

.empty-attachments {
  color: var(--color-text-tertiary);
}

.attachment-item {
  background: var(--color-surface);
  border-color: var(--color-border);
}

.attachment-name {
  color: var(--color-text-primary);
}

.attachment-path {
  color: var(--color-text-secondary);
}

.attachment-size {
  color: var(--color-text-tertiary);
}

.btn-view-attachment:hover {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  border-color: var(--color-primary);
}

.btn-remove-attachment:hover {
  background: color-mix(in srgb, var(--color-error) 10%, transparent);
  border-color: var(--color-error);
  color: var(--color-error);
}

.attachments-error {
  background: color-mix(in srgb, var(--color-error) 10%, transparent);
  border-color: var(--color-error);
  color: var(--color-error);
}

.settings-slide-enter-active,
.settings-slide-leave-active {
  transition: all 0.3s ease;
}

.settings-slide-enter-from,
.settings-slide-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-10px);
  overflow: hidden;
}

/* Modal styles */
.modal-overlay {
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
}

.modal-container {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}

.modal-header {
  background: var(--color-surface);
  border-color: var(--color-border);
}

.modal-title {
  color: var(--color-text-primary);
}

.modal-path {
  background: color-mix(in srgb, var(--color-primary) 5%, transparent);
  border-color: var(--color-border);
  color: var(--color-text-secondary);
}

.modal-content {
  background: var(--color-surface);
}

.content-pre {
  color: var(--color-text-primary);
  font-family: 'Courier New', Courier, monospace;
}

.btn-close-modal {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}

.btn-close-modal:hover {
  background: color-mix(in srgb, var(--color-primary) 20%, transparent);
  border-color: var(--color-primary);
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-active .modal-container,
.modal-fade-leave-active .modal-container {
  transition: transform 0.3s ease;
}

.modal-fade-enter-from .modal-container,
.modal-fade-leave-to .modal-container {
  transform: scale(0.9);
}
</style>
