import { ref } from 'vue'
import apiService from '../services/apiService.js'
import { ENDPOINTS } from '../config/endpoints.js'

/**
 * Composable for managing cell fragments
 * @returns {Object} Fragment state and methods
 */
export function useFragmentManagement() {
  const showFragments = ref(false)
  const isFragmentModalOpen = ref(false)
  const isSavingFragment = ref(false)
  const fragmentModalError = ref(null)

  /**
   * Toggle fragments visibility
   */
  function toggleFragments() {
    showFragments.value = !showFragments.value
  }

  /**
   * Open fragment editor modal
   */
  function openFragmentModal(activeCell) {
    if (!activeCell || !activeCell.id) {
      console.warn('Não é possível adicionar fragmento a uma célula não salva')
      return false
    }

    isFragmentModalOpen.value = true
    fragmentModalError.value = null
    return true
  }

  /**
   * Close fragment editor modal
   */
  function closeFragmentModal() {
    isFragmentModalOpen.value = false
    fragmentModalError.value = null
  }

  /**
   * Save fragment to cell
   */
  async function saveFragment(activeCell, fragmentContent) {
    if (!activeCell || !activeCell.id) {
      fragmentModalError.value = 'Célula inválida'
      throw new Error('Invalid cell')
    }

    isSavingFragment.value = true
    fragmentModalError.value = null

    try {
      const newFragment = {
        tipo: 'memoria',
        conteudo: fragmentContent,
        resultado: null,
      }

      const updatedFragments = [...(activeCell.fragments || []), newFragment]

      const response = await apiService.fetch(
        ENDPOINTS.updateCell(activeCell.id),
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            fragments: updatedFragments,
          }),
        },
      )

      if (!response.ok) {
        throw new Error('Falha ao salvar fragmento')
      }

      const updatedCell = await response.json()

      // Close modal
      isFragmentModalOpen.value = false

      // Show fragments if not already visible
      if (!showFragments.value) {
        showFragments.value = true
      }

      return updatedCell
    } catch (error) {
      console.error('Erro ao salvar fragmento:', error)
      fragmentModalError.value = `Erro ao salvar fragmento: ${error.message}`
      throw error
    } finally {
      isSavingFragment.value = false
    }
  }

  return {
    // State
    showFragments,
    isFragmentModalOpen,
    isSavingFragment,
    fragmentModalError,

    // Methods
    toggleFragments,
    openFragmentModal,
    closeFragmentModal,
    saveFragment,
  }
}
