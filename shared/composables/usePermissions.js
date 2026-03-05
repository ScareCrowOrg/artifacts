/**
 * usePermissions Composable
 *
 * Composable para verificação de permissões em componentes Vue.
 * Fornece interface conveniente para verificar permissões do usuário.
 *
 * @module composables/usePermissions
 * @example
 * ```vue
 * <script setup>
 * import { usePermissions } from '@/composables/usePermissions'
 *
 * const { can, canAny, isAdmin } = usePermissions()
 *
 * if (can('cells.delete_any')) {
 *   // Mostrar botão de deletar tudo
 * }
 * </script>
 * ```
 */

import { computed } from 'vue'
import { usePermissionsStore } from '../stores/permissions.js'

/**
 * Composable para verificação de permissões.
 * @returns {Object} Métodos e computed properties para verificar permissões
 */
export function usePermissions() {
  const permissionsStore = usePermissionsStore()

  /**
   * Verifica se usuário tem permissão específica.
   * @param {string} permission
   * @returns {boolean}
   */
  const can = (permission) => {
    return permissionsStore.hasPermission(permission)
  }

  /**
   * Verifica se usuário tem qualquer uma das permissões.
   * @param {string[]} permissions
   * @returns {boolean}
   */
  const canAny = (permissions) => {
    return permissionsStore.hasAnyPermission(permissions)
  }

  /**
   * Verifica se usuário tem todas as permissões.
   * @param {string[]} permissions
   * @returns {boolean}
   */
  const canAll = (permissions) => {
    return permissionsStore.hasAllPermissions(permissions)
  }

  /**
   * Computed: verifica se usuário é admin.
   */
  const isAdmin = computed(() => permissionsStore.isAdmin)

  /**
   * Computed: verifica se usuário é user.
   */
  const isUser = computed(() => permissionsStore.isUser)

  /**
   * Computed: verifica se usuário é viewer.
   */
  const isViewer = computed(() => permissionsStore.isViewer)

  /**
   * Computed: verifica se usuário pode acessar painel admin.
   */
  const canAccessAdmin = computed(() => permissionsStore.canAccessAdminPanel)

  return {
    // Métodos
    can,
    canAny,
    canAll,

    // Computed
    isAdmin,
    isUser,
    isViewer,
    canAccessAdmin,
  }
}
