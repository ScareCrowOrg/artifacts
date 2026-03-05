/**
 * Cell Display Composable
 *
 * Provides formatting and CSS rules for cell display in the UI.
 * Updated to work with NotebookItem structure (initial_data instead of data).
 *
 * @module composables/useCellDisplay
 */

import { getNotebookItemTypeId } from '../types/notebook.js'

/**
 * Composable for cell display logic
 * @param {Object} cellTypesMap - Map of cell type ID to cell type object
 * @returns {Object} Display formatting functions
 */
export function useCellDisplay(cellTypesMap = null) {
  /**
   * Get display name for a cell or book (uses initial_data for cells, name for books).
   * @param {ICelula|ILivro} cell - The cell or book object.
   * @returns {string} The display name for the cell or book.
   */
  function getCellDisplayName(cell) {
    // Support both initial_data (new) and data (legacy)
    const data = cell.initial_data || cell.data || {}

    if (data.title) {
      return data.title
    }
    if (data.fileName) {
      return data.fileName
    }
    // For books, use name field
    if (cell.name) {
      return cell.name
    }
    if (cell.name) return cell.name
    if (cell.titulo) return cell.titulo

    // Fallback to cell ID
    if (cell.id && cell.id.length > 0) {
      return `Célula ${cell.id.substring(0, 8)}`
    }

    return 'Célula nova'
  }

  /**
   * Get icon for a cell based on its type (uses notebook_item_type_id)
   */
  function getCellIcon(cell, cellTypes = cellTypesMap) {
    if (!cellTypes) return '📦'

    const typeId = getNotebookItemTypeId(cell)
    const cellType = cellTypes.get ? cellTypes.get(typeId) : cellTypes[typeId]
    if (cellType?.icon) {
      // Map MDI icons to emojis
      const iconMap = {
        'mdi-text-box': '📝',
        'mdi-file-edit': '📄',
        'mdi-code': '💻',
        'mdi-database': '💾',
        'mdi-book': '📚',
        'mdi-lightbulb': '💡',
        'mdi-flask': '🧪',
      }
      return iconMap[cellType.icon] || '📦'
    }
    return '📦'
  }

  /**
   * Get category for a cell based on its type (uses notebook_item_type_id)
   */
  function getCellCategory(cell, cellTypes = cellTypesMap) {
    if (!cellTypes) return '💾 Persistida'

    const typeId = getNotebookItemTypeId(cell)
    const cellType = cellTypes.get ? cellTypes.get(typeId) : cellTypes[typeId]
    if (cellType?.category === 'efemera') {
      return '⚡ Efêmera'
    }
    return '💾 Persistida'
  }

  /**
   * Get CSS class for a cell category badge (uses notebook_item_type_id)
   */
  function getCellCategoryClass(cell, cellTypes = cellTypesMap) {
    if (!cellTypes) return 'bg-success/10 border border-success/30 text-success'

    const typeId = getNotebookItemTypeId(cell)
    const cellType = cellTypes.get ? cellTypes.get(typeId) : cellTypes[typeId]
    return cellType?.category === 'efemera'
      ? 'bg-warning/10 border border-warning/30 text-warning'
      : 'bg-success/10 border border-success/30 text-success'
  }

  /**
   * Format date for display (supports both created_at and dataCriacao)
   */
  function formatDate(dateString) {
    if (!dateString) return ''
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'agora'
    if (diffMins < 60) return `${diffMins}min`
    if (diffHours < 24) return `${diffHours}h`
    if (diffDays < 7) return `${diffDays}d`

    return date.toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
    })
  }

  /**
   * Get icon for a book
   */
  function getBookIcon(book) {
    if (book.isVirtual) return '📝'
    if (book.is_canonical_system_book) return '⚙️'
    if (book.is_unclassified_master_template) return '📋'
    return '📚'
  }

  return {
    getCellDisplayName,
    getCellIcon,
    getCellCategory,
    getCellCategoryClass,
    formatDate,
    getBookIcon,
  }
}
