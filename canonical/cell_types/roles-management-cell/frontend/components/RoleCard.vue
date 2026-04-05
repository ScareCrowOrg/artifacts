/**
 * @file RoleCard.vue
 * @description Card component for displaying a single role
 */
<template>
  <div class="role-card">
    <div class="card-header">
      <h3 class="role-name">{{ role.name }}</h3>
      <div class="card-actions">
        <button
          class="btn-icon"
          :aria-label="$t('common.edit')"
          @click="$emit('edit', role)"
        >
          ✏️
        </button>
        <button
          class="btn-icon btn-danger"
          :aria-label="$t('common.delete')"
          @click="$emit('delete', role)"
        >
          🗑️
        </button>
      </div>
    </div>

    <p v-if="role.description" class="role-description">
      {{ role.description }}
    </p>

    <div class="role-meta">
      <div class="meta-item">
        <span class="meta-label">
          {{ $t('cells.rolesManagement.permissions') }}:
        </span>
        <span class="meta-value badge">
          {{ role.permissions.length }}
        </span>
      </div>
      <div v-if="role.user_count !== undefined" class="meta-item">
        <span class="meta-label">
          {{ $t('cells.rolesManagement.users') }}:
        </span>
        <span class="meta-value">
          {{ role.user_count }}
        </span>
      </div>
    </div>

    <div class="permissions-preview">
      <span
        v-for="perm in previewPermissions"
        :key="perm"
        class="permission-tag"
      >
        {{ perm }}
      </span>
      <span v-if="remainingCount > 0" class="more-tag">
        +{{ remainingCount }} {{ $t('common.more') }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Role } from '../composables/useRolesManagement'

// Props
const props = defineProps<{
  role: Role
}>()

// Emits
defineEmits<{
  edit: [role: Role]
  delete: [role: Role]
}>()

// I18n
const { t } = useI18n()

// Preview first 3 permissions
const previewPermissions = computed(() => props.role.permissions.slice(0, 3))
const remainingCount = computed(() => Math.max(0, props.role.permissions.length - 3))
</script>

<style scoped>
.role-card {
  background: var(--color-background-secondary);
  border: 1px solid var(--color-border);
  border-radius: 0.5rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  transition: all 0.2s;
}

.role-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 0.5rem;
}

.role-name {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
  color: var(--color-text);
}

.card-actions {
  display: flex;
  gap: 0.25rem;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.1rem;
  padding: 0.25rem;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.btn-icon:hover {
  opacity: 1;
}

.btn-danger:hover {
  filter: brightness(1.2);
}

.role-description {
  font-size: 0.9rem;
  color: var(--color-text-secondary);
  margin: 0;
  line-height: 1.4;
}

.role-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.85rem;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.meta-label {
  color: var(--color-text-secondary);
}

.meta-value {
  color: var(--color-text);
  font-weight: 500;
}

.meta-value.badge {
  background: var(--color-primary);
  color: white;
  padding: 0.125rem 0.5rem;
  border-radius: 1rem;
  font-size: 0.8rem;
}

.permissions-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.permission-tag,
.more-tag {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  background: var(--color-background);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}

.more-tag {
  font-weight: 500;
  color: var(--color-primary);
}
</style>
