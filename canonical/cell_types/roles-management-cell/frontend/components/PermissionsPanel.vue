/**
 * @file PermissionsPanel.vue
 * @description Interactive panel for selecting permissions
 */
<template>
  <div class="permissions-panel">
    <!-- Search -->
    <div class="panel-toolbar">
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        :placeholder="$t('cells.rolesManagement.searchPermissions')"
      />
      <select v-model="selectedCategory" class="category-select">
        <option value="">{{ $t('cells.rolesManagement.allCategories') }}</option>
        <option v-for="cat in categories" :key="cat" :value="cat">
          {{ cat }}
        </option>
      </select>
    </div>

    <!-- Permission Groups -->
    <div class="permissions-groups">
      <div
        v-for="group in permissionGroups"
        :key="group.category"
        class="permission-group"
      >
        <div class="group-header">
          <label class="group-label">
            <input
              type="checkbox"
              :checked="isGroupSelected(group)"
              :indeterminate.prop="isGroupIndeterminate(group)"
              @change="toggleGroup(group, $event)"
              class="group-checkbox"
            />
            <span class="group-name">{{ group.category }}</span>
            <span class="group-count">({{ group.permissions.length }})</span>
          </label>
        </div>

        <div class="group-permissions">
          <label
            v-for="permission in group.permissions"
            :key="permission.id"
            class="permission-label"
          >
            <input
              type="checkbox"
              :value="permission.id"
              :checked="modelValue.includes(permission.id)"
              @change="togglePermission(permission.id)"
              class="permission-checkbox"
            />
            <div class="permission-info">
              <span class="permission-name">{{ permission.name }}</span>
              <span class="permission-description">{{ permission.description }}</span>
            </div>
          </label>
        </div>
      </div>
    </div>

    <!-- Selection Summary -->
    <div class="selection-summary">
      {{ $t('cells.rolesManagement.permissionsSelected', { count: modelValue.length }) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePermissionsData } from '../composables/usePermissionsData'
import type { PermissionGroup } from '../composables/usePermissionsData'

// Props
const props = defineProps<{
  modelValue: string[]
}>()

// Emits
const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

// I18n
const { t } = useI18n()

// Permissions data
const {
  categories,
  permissionGroups,
  searchQuery,
  selectedCategory
} = usePermissionsData()

/**
 * Check if entire group is selected
 */
function isGroupSelected(group: PermissionGroup): boolean {
  return group.permissions.every(p => props.modelValue.includes(p.id))
}

/**
 * Check if group is partially selected (indeterminate)
 */
function isGroupIndeterminate(group: PermissionGroup): boolean {
  const selected = group.permissions.filter(p => props.modelValue.includes(p.id))
  return selected.length > 0 && selected.length < group.permissions.length
}

/**
 * Toggle entire group
 */
function toggleGroup(group: PermissionGroup, event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  const groupPermissionIds = group.permissions.map(p => p.id)
  
  if (checked) {
    // Add all permissions from group
    const newValue = [...new Set([...props.modelValue, ...groupPermissionIds])]
    emit('update:modelValue', newValue)
  } else {
    // Remove all permissions from group
    const newValue = props.modelValue.filter(id => !groupPermissionIds.includes(id))
    emit('update:modelValue', newValue)
  }
}

/**
 * Toggle single permission
 */
function togglePermission(permissionId: string): void {
  const newValue = props.modelValue.includes(permissionId)
    ? props.modelValue.filter(id => id !== permissionId)
    : [...props.modelValue, permissionId]
  
  emit('update:modelValue', newValue)
}
</script>

<style scoped>
.permissions-panel {
  border: 1px solid var(--color-border);
  border-radius: 0.375rem;
  background: var(--color-background-secondary);
  padding: 1rem;
  max-height: 500px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.panel-toolbar {
  display: flex;
  gap: 0.5rem;
}

.search-input {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 0.375rem;
  background: var(--color-background);
  color: var(--color-text);
  font-size: 0.9rem;
}

.category-select {
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 0.375rem;
  background: var(--color-background);
  color: var(--color-text);
  font-size: 0.9rem;
}

.permissions-groups {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.permission-group {
  border: 1px solid var(--color-border);
  border-radius: 0.375rem;
  background: var(--color-background);
}

.group-header {
  padding: 0.75rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-background-secondary);
}

.group-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-weight: 500;
}

.group-checkbox {
  cursor: pointer;
}

.group-name {
  text-transform: capitalize;
  color: var(--color-text);
}

.group-count {
  color: var(--color-text-secondary);
  font-size: 0.9rem;
}

.group-permissions {
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.permission-label {
  display: flex;
  align-items: start;
  gap: 0.5rem;
  padding: 0.5rem;
  border-radius: 0.25rem;
  cursor: pointer;
  transition: background 0.2s;
}

.permission-label:hover {
  background: var(--color-background-hover);
}

.permission-checkbox {
  margin-top: 0.25rem;
  cursor: pointer;
}

.permission-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.permission-name {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--color-text);
}

.permission-description {
  font-size: 0.85rem;
  color: var(--color-text-secondary);
}

.selection-summary {
  padding: 0.75rem;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border-radius: 0.375rem;
  text-align: center;
  font-weight: 500;
  font-size: 0.9rem;
}
</style>
