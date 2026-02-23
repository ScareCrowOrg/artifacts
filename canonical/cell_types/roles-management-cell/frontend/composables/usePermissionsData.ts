/**
 * @file usePermissionsData.ts
 * @description Composable for permissions data and metadata
 * 
 * Provides permission definitions, grouping, and helper methods
 * for working with system permissions.
 */

import { ref, computed } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('composables:usePermissionsData')

/**
 * Permission definition interface
 */
export interface Permission {
  id: string
  name: string
  description: string
  category: string
}

/**
 * Permission group interface
 */
export interface PermissionGroup {
  name: string
  category: string
  permissions: Permission[]
}

/**
 * Available system permissions
 */
const SYSTEM_PERMISSIONS: Permission[] = [
  // Cell permissions
  { id: 'cells:read', name: 'Read Cells', description: 'View cells in notebooks', category: 'cells' },
  { id: 'cells:create', name: 'Create Cells', description: 'Create new cells', category: 'cells' },
  { id: 'cells:update', name: 'Update Cells', description: 'Edit existing cells', category: 'cells' },
  { id: 'cells:delete', name: 'Delete Cells', description: 'Remove cells', category: 'cells' },
  { id: 'cells:execute', name: 'Execute Cells', description: 'Run cell operations', category: 'cells' },
  
  // Book permissions
  { id: 'books:read', name: 'Read Books', description: 'View notebooks/books', category: 'books' },
  { id: 'books:create', name: 'Create Books', description: 'Create new notebooks', category: 'books' },
  { id: 'books:update', name: 'Update Books', description: 'Edit notebooks', category: 'books' },
  { id: 'books:delete', name: 'Delete Books', description: 'Remove notebooks', category: 'books' },
  
  // User permissions
  { id: 'users:read', name: 'Read Users', description: 'View user information', category: 'users' },
  { id: 'users:create', name: 'Create Users', description: 'Add new users', category: 'users' },
  { id: 'users:update', name: 'Update Users', description: 'Edit user profiles', category: 'users' },
  { id: 'users:delete', name: 'Delete Users', description: 'Remove users', category: 'users' },
  
  // Role permissions
  { id: 'roles:read', name: 'Read Roles', description: 'View role definitions', category: 'roles' },
  { id: 'roles:admin', name: 'Admin Roles', description: 'Full role management', category: 'roles' },
  
  // Content permissions
  { id: 'content:read', name: 'Read Content', description: 'View content items', category: 'content' },
  { id: 'content:create', name: 'Create Content', description: 'Upload content', category: 'content' },
  { id: 'content:update', name: 'Update Content', description: 'Edit content', category: 'content' },
  { id: 'content:delete', name: 'Delete Content', description: 'Remove content', category: 'content' },
  
  // System permissions
  { id: 'system:configure', name: 'Configure System', description: 'Modify system settings', category: 'system' },
  { id: 'system:monitor', name: 'Monitor System', description: 'View system metrics', category: 'system' },
  
  // AI Model permissions
  { id: 'ai_models:use', name: 'Use AI Models', description: 'Execute AI operations', category: 'ai_models' },
  { id: 'ai_models:configure', name: 'Configure AI', description: 'Manage AI settings', category: 'ai_models' }
]

/**
 * Permissions data composable
 */
export function usePermissionsData() {
  // State
  const searchQuery = ref('')
  const selectedCategory = ref<string | null>(null)

  // All permissions
  const permissions = computed(() => SYSTEM_PERMISSIONS)

  // Permission categories
  const categories = computed(() => {
    const cats = new Set(SYSTEM_PERMISSIONS.map(p => p.category))
    return Array.from(cats).sort()
  })

  // Filtered permissions
  const filteredPermissions = computed(() => {
    let result = SYSTEM_PERMISSIONS
    
    // Filter by category
    if (selectedCategory.value) {
      result = result.filter(p => p.category === selectedCategory.value)
    }
    
    // Filter by search query
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      result = result.filter(p => 
        p.id.toLowerCase().includes(query) ||
        p.name.toLowerCase().includes(query) ||
        p.description.toLowerCase().includes(query)
      )
    }
    
    return result
  })

  // Grouped permissions
  const permissionGroups = computed(() => {
    const groups: Record<string, PermissionGroup> = {}
    
    filteredPermissions.value.forEach(permission => {
      if (!groups[permission.category]) {
        groups[permission.category] = {
          name: permission.category,
          category: permission.category,
          permissions: []
        }
      }
      groups[permission.category].permissions.push(permission)
    })
    
    return Object.values(groups).sort((a, b) => a.name.localeCompare(b.name))
  })

  /**
   * Get permission by ID
   */
  function getPermissionById(id: string): Permission | undefined {
    return SYSTEM_PERMISSIONS.find(p => p.id === id)
  }

  /**
   * Get permissions by category
   */
  function getPermissionsByCategory(category: string): Permission[] {
    return SYSTEM_PERMISSIONS.filter(p => p.category === category)
  }

  /**
   * Check if permission exists
   */
  function hasPermission(id: string): boolean {
    return SYSTEM_PERMISSIONS.some(p => p.id === id)
  }

  /**
   * Clear filters
   */
  function clearFilters(): void {
    searchQuery.value = ''
    selectedCategory.value = null
  }

  return {
    // State
    searchQuery,
    selectedCategory,
    
    // Computed
    permissions,
    categories,
    filteredPermissions,
    permissionGroups,
    
    // Methods
    getPermissionById,
    getPermissionsByCategory,
    hasPermission,
    clearFilters
  }
}
