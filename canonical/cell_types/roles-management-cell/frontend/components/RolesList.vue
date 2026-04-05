/**
 * @file RolesList.vue
 * @description List view component for roles with search, filter, and actions
 */
<template>
  <div class="roles-list">
    <!-- Toolbar -->
    <div class="list-toolbar">
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        :placeholder="$t('cells.rolesManagement.searchPlaceholder')"
      />
      <button class="btn-refresh" @click="$emit('refresh')" :disabled="loading">
        🔄 {{ $t('common.refresh') }}
      </button>
      <button class="btn-create" @click="handleCreate">
        ➕ {{ $t('cells.rolesManagement.createRole') }}
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading && roles.length === 0" class="loading-state">
      <div class="loading-spinner"></div>
      <p>{{ $t('common.loading') }}</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredRoles.length === 0" class="empty-state">
      <div class="empty-icon">📋</div>
      <p>{{ $t('cells.rolesManagement.noRoles') }}</p>
    </div>

    <!-- Roles Grid -->
    <div v-else class="roles-grid">
      <RoleCard
        v-for="role in filteredRoles"
        :key="role.id"
        :role="role"
        @edit="$emit('edit', role)"
        @delete="$emit('delete', role)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Role } from '../composables/useRolesManagement'
import RoleCard from './RoleCard.vue'

// Props
const props = defineProps<{
  roles: Role[]
  loading: boolean
}>()

// Emits
const emit = defineEmits<{
  edit: [role: Role | null]
  delete: [role: Role]
  refresh: []
}>()

// I18n
const { t } = useI18n()

// State
const searchQuery = ref('')

/**
 * Filtered roles based on search
 */
const filteredRoles = computed(() => {
  if (!searchQuery.value) {
    return props.roles
  }
  
  const query = searchQuery.value.toLowerCase()
  return props.roles.filter(role =>
    role.name.toLowerCase().includes(query) ||
    role.description?.toLowerCase().includes(query) ||
    role.permissions.some(p => p.toLowerCase().includes(query))
  )
})

/**
 * Handle create new role
 */
function handleCreate(): void {
  emit('edit', null)
}
</script>

<style scoped>
.roles-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: 100%;
}

.list-toolbar {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.search-input {
  flex: 1;
  padding: 0.5rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 0.375rem;
  background: var(--color-background);
  color: var(--color-text);
  font-size: 0.95rem;
}

.search-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.btn-refresh,
.btn-create {
  padding: 0.5rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 0.375rem;
  background: var(--color-background-secondary);
  color: var(--color-text);
  cursor: pointer;
  font-size: 0.95rem;
  white-space: nowrap;
}

.btn-refresh:hover,
.btn-create:hover {
  background: var(--color-background-hover);
}

.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-create {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.btn-create:hover {
  background: var(--color-primary-hover);
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: var(--color-text-secondary);
}

.loading-spinner {
  width: 3rem;
  height: 3rem;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.roles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
  overflow-y: auto;
}
</style>
