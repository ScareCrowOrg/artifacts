/**
 * Permissions Store
 *
 * Manages user permissions and roles centrally using Pinia.
 * Integrates with auth store to automatically load/clear permissions on login/logout.
 *
 * @module stores/permissions
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth.js'

export const usePermissionsStore = defineStore('permissions', () => {
  const authStore = useAuthStore()

  // ========== State ==========
  const userPermissions = ref([])
  const userRoles = ref([])
  const isLoading = ref(false)

  // ========== Computed ==========
  const isAdmin = computed(() => {
    return userRoles.value.includes('admin')
  })

  const isUser = computed(() => {
    return userRoles.value.includes('user') || isAdmin.value
  })

  const isViewer = computed(() => {
    return userRoles.value.includes('viewer') || isUser.value
  })

  const canAccessAdminPanel = computed(() => {
    return isAdmin.value || userPermissions.value.includes('system.configure')
  })

  // ========== Actions ==========

  /**
   * Carrega permissões do usuário autenticado.
   * Atualiza state com roles e permissões.
   */
  function loadUserPermissions() {
    const user = authStore.currentUser

    if (!user) {
      userPermissions.value = []
      userRoles.value = []
      return
    }

    // Carrega roles do usuário
    userRoles.value = user.roles || ['user']

    // Calcula permissões baseado em roles
    // Para MVP, usa mapeamento estático
    // Futuro: carregar do backend via API
    userPermissions.value = getPermissionsForRoles(userRoles.value)
  }

  /**
   * Verifica se usuário tem permissão específica.
   * @param {string} permission - Nome da permissão (ex: "cells.create")
   * @returns {boolean}
   */
  function hasPermission(permission) {
    if (isAdmin.value) return true // Admin tem tudo
    if (userPermissions.value.includes('*')) return true // Wildcard
    return userPermissions.value.includes(permission)
  }

  /**
   * Verifica se usuário tem qualquer uma das permissões.
   * @param {string[]} permissions - Lista de permissões
   * @returns {boolean}
   */
  function hasAnyPermission(permissions) {
    if (isAdmin.value) return true
    return permissions.some((p) => hasPermission(p))
  }

  /**
   * Verifica se usuário tem todas as permissões.
   * @param {string[]} permissions - Lista de permissões
   * @returns {boolean}
   */
  function hasAllPermissions(permissions) {
    if (isAdmin.value) return true
    return permissions.every((p) => hasPermission(p))
  }

  /**
   * Mapeia roles para permissões (MVP - mapeamento estático).
   * Futuramente pode vir do backend via API.
   * @param {string[]} roles - Lista de roles
   * @returns {string[]} - Lista de permissões
   */
  function getPermissionsForRoles(roles) {
    const rolePermissions = {
      admin: ['*'], // Todas as permissões
      user: [
        'cells.create',
        'cells.read_own',
        'cells.update_own',
        'cells.delete_own',
        'books.create',
        'books.read_own',
        'books.update_own',
        'books.delete_own',
        'users.read_own',
        'ai_models.use',
      ],
      viewer: ['cells.read_any', 'books.read_any', 'users.read_own'],
      guest: [],
    }

    const permissions = new Set()
    roles.forEach((role) => {
      const perms = rolePermissions[role] || []
      perms.forEach((p) => permissions.add(p))
    })

    return Array.from(permissions)
  }

  // ========== Watchers ==========

  // Atualiza permissões quando usuário logar/deslogar
  watch(
    () => authStore.isAuthenticated,
    (isAuth) => {
      if (isAuth) {
        loadUserPermissions()
      } else {
        userPermissions.value = []
        userRoles.value = []
      }
    },
    { immediate: true },
  )

  // ========== Return ==========
  return {
    // State
    userPermissions,
    userRoles,
    isLoading,

    // Computed
    isAdmin,
    isUser,
    isViewer,
    canAccessAdminPanel,

    // Actions
    loadUserPermissions,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
  }
})
