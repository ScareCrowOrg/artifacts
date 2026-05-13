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
 * @file RoleEditor.vue
 * @description Form for creating and editing roles
 */
<template>
  <div class="role-editor">
    <h2 class="editor-title">
      {{ role ? $t('cells.rolesManagement.editRole') : $t('cells.rolesManagement.createRole') }}
    </h2>

    <form @submit.prevent="handleSubmit" class="editor-form">
      <!-- Role Name -->
      <div class="form-group">
        <label for="role-name" class="form-label">
          {{ $t('cells.rolesManagement.roleName') }}
          <span class="required">*</span>
        </label>
        <input
          id="role-name"
          v-model="formData.name"
          type="text"
          class="form-input"
          :placeholder="$t('cells.rolesManagement.roleNamePlaceholder')"
          required
        />
      </div>

      <!-- Role Description -->
      <div class="form-group">
        <label for="role-description" class="form-label">
          {{ $t('cells.rolesManagement.roleDescription') }}
        </label>
        <textarea
          id="role-description"
          v-model="formData.description"
          class="form-textarea"
          rows="3"
          :placeholder="$t('cells.rolesManagement.roleDescriptionPlaceholder')"
        ></textarea>
      </div>

      <!-- Permissions -->
      <div class="form-group">
        <label class="form-label">
          {{ $t('cells.rolesManagement.permissions') }}
          <span class="required">*</span>
        </label>
        <PermissionsPanel
          v-model="formData.permissions"
        />
      </div>

      <!-- Actions -->
      <div class="form-actions">
        <button
          type="button"
          class="btn btn-secondary"
          @click="$emit('cancel')"
          :disabled="loading"
        >
          {{ $t('common.cancel') }}
        </button>
        <button
          type="submit"
          class="btn btn-primary"
          :disabled="loading || !isValid"
        >
          {{ loading ? $t('common.saving') : $t('common.save') }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Role } from '../composables/useRolesManagement'
import type { RoleData } from '../RolesManagementCell'
import PermissionsPanel from './PermissionsPanel.vue'

// Props
const props = defineProps<{
  role: Role | null
  loading: boolean
}>()

// Emits
const emit = defineEmits<{
  save: [data: RoleData]
  cancel: []
}>()

// I18n
const { t } = useI18n()

// Form data
const formData = ref<RoleData>({
  name: '',
  permissions: [],
  description: ''
})

// Validation
const isValid = computed(() => {
  return formData.value.name.trim() !== '' &&
         formData.value.permissions.length > 0
})

/**
 * Handle form submit
 */
function handleSubmit(): void {
  if (!isValid.value) return
  emit('save', {
    name: formData.value.name.trim(),
    permissions: formData.value.permissions,
    description: formData.value.description?.trim() || undefined
  })
}

// Watch for role prop changes
watch(() => props.role, (newRole) => {
  if (newRole) {
    formData.value = {
      name: newRole.name,
      permissions: [...newRole.permissions],
      description: newRole.description || ''
    }
  } else {
    formData.value = {
      name: '',
      permissions: [],
      description: ''
    }
  }
}, { immediate: true })
</script>

<style scoped>
.role-editor {
  max-width: 800px;
  margin: 0 auto;
}

.editor-title {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0 0 1.5rem;
  color: var(--color-text);
}

.editor-form {
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
.form-textarea {
  padding: 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 0.375rem;
  background: var(--color-background);
  color: var(--color-text);
  font-size: 0.95rem;
  font-family: inherit;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--color-primary);
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
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

.btn-secondary {
  background: var(--color-background-secondary);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-background-hover);
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}
</style>
