/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
/**
 * @file View.vue
 * @description Main view component for Roles Management Cell
 * 
 * Provides tabbed interface for roles management:
 * - Roles List tab: View all roles
 * - Create/Edit tab: Create new or edit existing roles
 * - Assign Roles tab: Assign roles to users
 */
<template>
  <div class="roles-management-cell">
    <!-- Main Content -->
    <div class="roles-content">
      <!-- Header -->
      <div class="cell-header">
        <h1 class="cell-title">
          {{ $t('cells.rolesManagement.title') }}
        </h1>
        <button
          class="btn-close"
          :aria-label="$t('common.close')"
          @click="$emit('close')"
        >
          ✕
        </button>
      </div>

      <!-- Error Banner -->
      <div v-if="error" class="error-banner" role="alert">
        <span class="error-icon">⚠️</span>
        {{ error }}
        <button class="error-close" @click="clearError">✕</button>
      </div>

      <!-- Tabs -->
      <div class="tabs-nav">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'list' }"
          @click="activeTab = 'list'"
        >
          {{ $t('cells.rolesManagement.tabs.list') }}
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'editor' }"
          @click="activeTab = 'editor'"
        >
          {{ $t('cells.rolesManagement.tabs.editor') }}
          <span v-if="editingRole" class="tab-badge">
            {{ editingRole.name }}
          </span>
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'assign' }"
          @click="activeTab = 'assign'"
        >
          {{ $t('cells.rolesManagement.tabs.assign') }}
        </button>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">
        <!-- List Tab -->
        <RolesList
          v-if="activeTab === 'list'"
          :roles="roles"
          :loading="loading"
          @edit="handleEdit"
          @delete="handleDelete"
          @refresh="handleRefresh"
        />

        <!-- Editor Tab -->
        <RoleEditor
          v-if="activeTab === 'editor'"
          :role="editingRole"
          :loading="loading"
          @save="handleSave"
          @cancel="handleCancelEdit"
        />

        <!-- Assign Tab -->
        <AssignRoleModal
          v-if="activeTab === 'assign'"
          :roles="roles"
          :loading="loading"
          @assigned="handleAssigned"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRolesManagement } from './composables/useRolesManagement'
import type { Role } from './composables/useRolesManagement'
import type { RoleData } from './RolesManagementCell'
import RolesList from './components/RolesList.vue'
import RoleEditor from './components/RoleEditor.vue'
import AssignRoleModal from './components/AssignRoleModal.vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:RolesManagementView')

// Props
defineProps<{
  cellInstance?: {
    id: string
    initial_data?: Record<string, any>
  }
}>()

// Emits
const emit = defineEmits<{
  close: []
}>()

// I18n
const { t } = useI18n()

// Roles management
const {
  roles,
  loading,
  error,
  fetchRoles,
  createRole,
  updateRole,
  deleteRole,
  clearError
} = useRolesManagement()

// State
const activeTab = ref<'list' | 'editor' | 'assign'>('list')
const editingRole = ref<Role | null>(null)

/**
 * Handle edit role
 */
function handleEdit(role: Role | null): void {
  if (role) {
    editingRole.value = { ...role }
  } else {
    editingRole.value = null
  }
  activeTab.value = 'editor'
  log.debug('Editing role', { roleId: role?.id })
}

/**
 * Handle save role (create or update)
 */
async function handleSave(data: RoleData): Promise<void> {
  try {
    if (editingRole.value?.id) {
      // Update existing role
      await updateRole(editingRole.value.id, data)
      log.info('Role updated', { roleId: editingRole.value.id })
    } else {
      // Create new role
      await createRole(data)
      log.info('Role created', { name: data.name })
    }
    
    // Reset editor and switch to list
    editingRole.value = null
    activeTab.value = 'list'
    
    // Refresh roles list
    await fetchRoles()
  } catch (err: any) {
    log.error('Failed to save role', err)
    // Error is handled by composable
  }
}

/**
 * Handle cancel edit
 */
function handleCancelEdit(): void {
  editingRole.value = null
  activeTab.value = 'list'
  log.debug('Edit cancelled')
}

/**
 * Handle delete role
 */
async function handleDelete(role: Role): Promise<void> {
  if (!confirm(t('cells.rolesManagement.confirmDelete', { name: role.name }))) {
    return
  }
  
  try {
    await deleteRole(role.id)
    log.info('Role deleted', { roleId: role.id })
    await fetchRoles()
  } catch (err: any) {
    log.error('Failed to delete role', err)
  }
}

/**
 * Handle refresh
 */
async function handleRefresh(): Promise<void> {
  await fetchRoles()
}

/**
 * Handle role assigned
 */
async function handleAssigned(): Promise<void> {
  log.info('Role assigned successfully')
  // Could refresh roles to update user counts
}

// Load roles on mount
onMounted(async () => {
  await fetchRoles()
})
</script>

<style scoped>
.roles-management-cell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-background);
  color: var(--color-text);
}

.permission-denied {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 2rem;
  text-align: center;
}

.denied-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.roles-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.cell-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid var(--color-border);
}

.cell-title {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--color-text-secondary);
  padding: 0.5rem;
  line-height: 1;
}

.btn-close:hover {
  color: var(--color-text);
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: var(--color-error-bg);
  color: var(--color-error-text);
  border-left: 4px solid var(--color-error);
}

.error-icon {
  font-size: 1.25rem;
}

.error-close {
  margin-left: auto;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 1.25rem;
  padding: 0.25rem;
}

.tabs-nav {
  display: flex;
  gap: 0.5rem;
  padding: 1rem 1rem 0;
  border-bottom: 1px solid var(--color-border);
}

.tab-btn {
  padding: 0.75rem 1.5rem;
  background: var(--color-background-secondary);
  border: 1px solid var(--color-border);
  border-bottom: none;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--color-text-secondary);
  border-radius: 0.5rem 0.5rem 0 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tab-btn:hover {
  background: var(--color-background-hover);
  color: var(--color-text);
}

.tab-btn.active {
  background: var(--color-background);
  color: var(--color-primary);
  border-bottom-color: var(--color-background);
  margin-bottom: -1px;
}

.tab-badge {
  padding: 0.25rem 0.5rem;
  background: var(--color-primary);
  color: white;
  border-radius: 0.25rem;
  font-size: 0.8rem;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}
</style>
