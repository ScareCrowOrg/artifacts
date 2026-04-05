/**
 * @file AssignRoleModal.vue
 * @description Modal for assigning roles to users
 */
<template>
  <div class="assign-role-modal">
    <h2 class="modal-title">{{ $t('cells.rolesManagement.assignRoles') }}</h2>

    <form @submit.prevent="handleSubmit" class="assign-form">
      <!-- User Selection -->
      <div class="form-group">
        <label for="user-select" class="form-label">
          {{ $t('cells.rolesManagement.selectUser') }}
          <span class="required">*</span>
        </label>
        <input
          id="user-search"
          v-model="userSearch"
          type="text"
          class="form-input"
          :placeholder="$t('cells.rolesManagement.searchUsers')"
          @input="searchUsers"
        />
        <select
          v-if="users.length > 0"
          v-model="selectedUserId"
          class="form-select"
          size="5"
        >
          <option
            v-for="user in users"
            :key="user.id"
            :value="user.id"
          >
            {{ user.name || user.email }} ({{ user.email }})
          </option>
        </select>
        <p v-if="loadingUsers" class="loading-text">
          {{ $t('common.loading') }}...
        </p>
      </div>

      <!-- Role Selection -->
      <div class="form-group">
        <label for="role-select" class="form-label">
          {{ $t('cells.rolesManagement.selectRole') }}
          <span class="required">*</span>
        </label>
        <select
          id="role-select"
          v-model="selectedRoleId"
          class="form-select"
          required
        >
          <option value="">{{ $t('cells.rolesManagement.chooseRole') }}</option>
          <option
            v-for="role in roles"
            :key="role.id"
            :value="role.id"
          >
            {{ role.name }}{{ role.description ? ` - ${role.description}` : '' }}
          </option>
        </select>
      </div>

      <!-- Current Assignment Info -->
      <div v-if="selectedUserId && userRoles" class="info-box">
        <p class="info-title">{{ $t('cells.rolesManagement.currentRoles') }}:</p>
        <div v-if="userRoles.length > 0" class="roles-badges">
          <span
            v-for="roleName in userRoles"
            :key="roleName"
            class="role-badge"
          >
            {{ roleName }}
          </span>
        </div>
        <p v-else class="no-roles">
          {{ $t('cells.rolesManagement.noRolesAssigned') }}
        </p>
      </div>

      <!-- Error Display -->
      <div v-if="error" class="error-box" role="alert">
        <span class="error-icon">⚠️</span>
        {{ error }}
      </div>

      <!-- Actions -->
      <div class="form-actions">
        <button
          type="submit"
          class="btn btn-primary"
          :disabled="loading || !selectedUserId || !selectedRoleId"
        >
          {{ loading ? $t('common.assigning') : $t('cells.rolesManagement.assignRole') }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRolesManagement } from '../composables/useRolesManagement'
import type { Role } from '../composables/useRolesManagement'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:AssignRoleModal')

// Props
const props = defineProps<{
  roles: Role[]
  loading: boolean
}>()

// Emits
const emit = defineEmits<{
  assigned: []
}>()

// I18n
const { t } = useI18n()

// Roles management
const { assignRole } = useRolesManagement()

// State
const userSearch = ref('')
const users = ref<any[]>([])
const loadingUsers = ref(false)
const selectedUserId = ref('')
const selectedRoleId = ref('')
const userRoles = ref<string[]>([])
const error = ref<string | null>(null)

/**
 * Search for users
 */
async function searchUsers(): Promise<void> {
  if (!userSearch.value || userSearch.value.length < 2) {
    users.value = []
    return
  }
  
  loadingUsers.value = true
  error.value = null
  
  try {
    const response = await apiFetch(
      `/api/users?search=${encodeURIComponent(userSearch.value)}&limit=10`
    )
    users.value = response
  } catch (err: any) {
    log.error('Failed to search users', err)
    error.value = t('cells.rolesManagement.errorSearchingUsers')
  } finally {
    loadingUsers.value = false
  }
}

/**
 * Load user's current roles
 */
async function loadUserRoles(userId: string): Promise<void> {
  try {
    const response = await apiFetch(`/api/users/${userId}`)
    userRoles.value = response.roles || []
  } catch (err: any) {
    log.error('Failed to load user roles', err)
  }
}

/**
 * Handle form submit
 */
async function handleSubmit(): Promise<void> {
  if (!selectedUserId.value || !selectedRoleId.value) return
  
  error.value = null
  
  try {
    await assignRole(selectedRoleId.value, selectedUserId.value)
    
    // Success - emit and reset
    emit('assigned')
    selectedUserId.value = ''
    selectedRoleId.value = ''
    userSearch.value = ''
    users.value = []
    userRoles.value = []
    
    log.info('Role assigned successfully')
  } catch (err: any) {
    error.value = err.message || t('cells.rolesManagement.errorAssigningRole')
  }
}

// Watch selected user to load their roles
watch(selectedUserId, (userId) => {
  if (userId) {
    loadUserRoles(userId)
  } else {
    userRoles.value = []
  }
})
</script>

<style scoped>
.assign-role-modal {
  max-width: 600px;
  margin: 0 auto;
}

.modal-title {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0 0 1.5rem;
  color: var(--color-text);
}

.assign-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--color-text);
}

.required {
  color: var(--color-error);
}

.form-input,
.form-select {
  padding: 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 0.375rem;
  background: var(--color-background);
  color: var(--color-text);
  font-size: 0.95rem;
  font-family: inherit;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.loading-text {
  font-size: 0.9rem;
  color: var(--color-text-secondary);
  font-style: italic;
}

.info-box {
  padding: 1rem;
  background: var(--color-background-secondary);
  border: 1px solid var(--color-border);
  border-radius: 0.375rem;
}

.info-title {
  font-size: 0.9rem;
  font-weight: 500;
  margin: 0 0 0.5rem;
  color: var(--color-text);
}

.roles-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.role-badge {
  padding: 0.25rem 0.75rem;
  background: var(--color-primary);
  color: white;
  border-radius: 1rem;
  font-size: 0.85rem;
  font-weight: 500;
}

.no-roles {
  font-size: 0.9rem;
  color: var(--color-text-secondary);
  margin: 0;
}

.error-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: var(--color-error-bg);
  color: var(--color-error-text);
  border-left: 4px solid var(--color-error);
  border-radius: 0.375rem;
}

.error-icon {
  font-size: 1.25rem;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border);
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}
</style>
